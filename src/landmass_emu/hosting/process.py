"""Servidor de partida como processo: um por sala em partida, porta UDP livre por partida, prontidão
pela tabela UDP do Windows (`netstat`) e encerramento ao fim da partida.

Prontidão: a porta aparece na tabela com o PID do próprio processo. Bind de teste depois do
lançamento disputaria a porta com o servidor, então não é usado. `PORT=` abre uma tentativa só
(tools/re/game_server_host.md §10): porta ocupada é falha, sem fallback.

Fim: `end` digita `exit` na janela para o motor gravar o `LOG=` da partida e só então derruba o
processo. `finish` derruba na hora (abandono e reinício de sala).

Equipamento (D190): antes do lançamento, a seção `[m<8 hex> LMEmuLoadout]` vai para o `LMEmu.ini`
da pasta de sistema do servidor; o motor lê na entrada de cada jogador. A seção sai em `end`,
`finish`, em falha de lançamento e quando o processo cai sozinho.
"""

import asyncio
import contextlib
import logging
import os
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from pathlib import Path
from subprocess import DEVNULL, PIPE
from uuid import uuid4

from landmass_emu.domain.match import MatchPlan
from landmass_emu.domain.match_stats import GameEndedPlayer
from landmass_emu.hosting.command import build_command, udp_listeners
from landmass_emu.hosting.control import MatchControl
from landmass_emu.hosting.game_end import parse_game_ended
from landmass_emu.hosting.loadout import LoadoutFile
from landmass_emu.hosting.window import send_exit
from landmass_emu.ports.match_host import GameEndpoint, MatchStartError

log = logging.getLogger(__name__)

POLL_SECONDS = 0.5
NETSTAT_TIMEOUT = 5.0
# shortcut: o motor saiu em ~0,1 s no teste de 13/10/2026; 8 s cobre partida maior. Se o log
# voltar cortado, subir este prazo antes de mexer no resto.
EXIT_GRACE_SECONDS = 8.0
EXE_NAME = "LandMass.exe"
LOADOUT_FILE = "LMEmu.ini"
CREATE_NO_WINDOW = 0x08000000

ExitCallback = Callable[[], Awaitable[None]]
ProcessFactory = Callable[[list[str], Path], Awaitable[asyncio.subprocess.Process]]
NetstatReader = Callable[[], Awaitable[str]]
ArgvBuilder = Callable[[MatchPlan, int, str], list[str]]
ExitSender = Callable[[int], bool]


@dataclass(frozen=True, slots=True)
class ProcessHostConfig:
    server_dir: Path  # pasta system\ do servidor-partida (contém LandMass.exe)
    game_host: str  # endereço anunciado no 403
    port_min: int
    port_max: int
    ready_timeout: float  # segundos até a porta aparecer na tabela UDP
    message_addr: str  # login_server=: endereço do Message Server
    version: int
    login_num: str


@dataclass(eq=False, slots=True)
class _Running:
    room_id: int
    port: int
    process: asyncio.subprocess.Process
    on_exit: ExitCallback
    log_name: str  # arquivo LOG= da partida, dentro de server_dir
    loadout_key: str  # seção da partida no LMEmu.ini
    ready: bool = False


class ProcessMatchHost:
    """`spawn`, `netstat`, `argv` e `exit_sender` são injetáveis: os testes usam processos de Python
    no lugar do LandMass.exe e não mandam tecla para janela alguma."""

    def __init__(
        self,
        config: ProcessHostConfig,
        *,
        spawn: ProcessFactory | None = None,
        netstat: NetstatReader | None = None,
        argv: ArgvBuilder | None = None,
        exit_sender: ExitSender | None = None,
    ) -> None:
        self._config = config
        self._spawn = spawn or _spawn_process
        self._netstat = netstat or _netstat_udp
        self._argv = argv or self._default_argv
        self._exit_sender = exit_sender or send_exit
        self._loadouts = LoadoutFile(config.server_dir / LOADOUT_FILE)
        self._running: dict[int, _Running] = {}
        self._watchers: set[asyncio.Task[None]] = set()
        self._control = MatchControl()

    async def command(self, room_id: int, line: str) -> bool:
        """Repassa `line` ao LMEmu da partida da sala (D254). Falso sem partida ou sem conexão."""
        match = self._running.get(room_id)
        return match is not None and await self._control.send(match.loadout_key, line)

    async def start(self, room_id: int, plan: MatchPlan, on_exit: ExitCallback) -> GameEndpoint:
        self.finish(room_id)
        port = self._pick_port()
        token = uuid4().hex[:8]
        log_name = f"partida-{port}-{token}.log"
        key = f"m{token}"
        try:
            self._loadouts.write(key, [*plan.loadout, *plan.loadout_extra])
        except OSError as e:
            raise MatchStartError(f"LMEmu.ini não gravado: {e}") from e
        try:
            plan = replace(plan, lmemu_key=key, control_port=await self._control.port())
            process = await self._spawn(self._argv(plan, port, log_name), self._config.server_dir)
        except BaseException:
            self._loadouts.remove(key)
            raise
        match = _Running(room_id, port, process, on_exit, log_name, key)
        self._running[room_id] = match
        watcher = asyncio.create_task(self._watch(match))
        self._watchers.add(watcher)
        watcher.add_done_callback(self._watchers.discard)
        try:
            await self._wait_ready(match)
        except MatchStartError:
            self.finish(room_id)
            raise
        match.ready = True
        log.info("partida da sala %d: %s pronta na porta UDP %d", room_id, plan.game_class, port)
        return GameEndpoint(self._config.game_host, port)

    def finish(self, room_id: int) -> None:
        match = self._running.pop(room_id, None)
        if match is None:
            return
        if match.process.returncode is None:
            # No Windows, terminar processo já encerrado levanta PermissionError (OSError).
            with contextlib.suppress(OSError):
                match.process.terminate()
        self._loadouts.remove(match.loadout_key)
        log.info("partida da sala %d: servidor encerrado (porta %d)", room_id, match.port)

    async def end(self, room_id: int) -> tuple[GameEndedPlayer, ...]:
        """Encerra o servidor da sala pelo console (`exit`), espera o motor gravar o log e devolve
        os jogadores do bloco `GameEnded` do `LOG=`. Sem janela para digitar, ou se o motor não sair
        no prazo, derruba o processo e o log fica com o que já foi descarregado. Sem servidor ou sem
        bloco, devolve vazio."""
        match = self._running.pop(room_id, None)
        if match is None:
            return ()
        if match.process.returncode is None and self._exit_sender(match.process.pid):
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(match.process.wait(), EXIT_GRACE_SECONDS)
        if match.process.returncode is None:
            with contextlib.suppress(OSError):
                match.process.terminate()
            await match.process.wait()
        self._loadouts.remove(match.loadout_key)
        log.info("partida da sala %d: servidor encerrado (porta %d)", room_id, match.port)
        return parse_game_ended(self._read_log(match.log_name) or "")

    async def close(self) -> None:
        for room_id in list(self._running):
            self.finish(room_id)
        await self._control.close()

    def _default_argv(self, plan: MatchPlan, port: int, log_name: str) -> list[str]:
        return build_command(
            self._config.server_dir / EXE_NAME,
            plan,
            port=port,
            message_addr=self._config.message_addr,
            version=self._config.version,
            login_num=self._config.login_num,
            log_file=log_name,
        )

    def _read_log(self, name: str) -> str | None:
        try:
            return (self._config.server_dir / name).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def _pick_port(self) -> int:
        busy = {m.port for m in self._running.values()}
        for port in range(self._config.port_min, self._config.port_max + 1):
            if port not in busy and udp_port_free(port):
                return port
        raise MatchStartError("nenhuma porta UDP livre na faixa configurada")

    async def _wait_ready(self, match: _Running) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._config.ready_timeout
        while True:
            if match.process.returncode is not None:
                raise MatchStartError("servidor de partida encerrou antes de abrir a porta")
            if (match.port, match.process.pid) in udp_listeners(await self._netstat()):
                return
            if loop.time() >= deadline:
                raise MatchStartError(
                    f"servidor de partida não abriu a porta {match.port} em "
                    f"{self._config.ready_timeout:g} s"
                )
            await asyncio.sleep(POLL_SECONDS)

    async def _watch(self, match: _Running) -> None:
        await match.process.wait()
        if self._running.get(match.room_id) is not match:
            return  # encerrado por finish ou end: não é queda
        if not match.ready:
            del self._running[match.room_id]
            self._loadouts.remove(match.loadout_key)
            log.warning("servidor da sala %d encerrou antes de ficar pronto", match.room_id)
            return
        # Fim por tempo ou pontos também chega aqui: o LMEmu sai no fim (D253). A partida fica em
        # `_running` para o `end` do `on_exit` ler o bloco `GameEnded` do log.
        log.info("servidor de partida da sala %d encerrou sozinho", match.room_id)
        try:
            await match.on_exit()
        except Exception:
            log.exception("erro ao tratar a saída do servidor da sala %d", match.room_id)
        if self._running.get(match.room_id) is match:
            self.finish(match.room_id)


def udp_port_free(port: int) -> bool:
    """Bind de teste só antes do lançamento. Depois, a prontidão usa a tabela UDP."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


async def _spawn_process(argv: list[str], cwd: Path) -> asyncio.subprocess.Process:
    try:
        return await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            stdin=DEVNULL,
            stdout=DEVNULL,
            stderr=DEVNULL,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except OSError as e:
        raise MatchStartError(f"servidor de partida não iniciou: {e}") from e


async def _netstat_udp() -> str:
    proc = await asyncio.create_subprocess_exec(
        "netstat", "-ano", "-p", "UDP", stdout=PIPE, stderr=DEVNULL
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), NETSTAT_TIMEOUT)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return ""
    return out.decode("cp850", errors="replace")
