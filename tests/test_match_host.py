"""Servidor de partida como processo, com processos Python no lugar do LandMass.exe: prontidão pela
tabela UDP, falha de início, encerramento e queda depois de pronto. Usa portas 48200..48219."""

import asyncio
import socket
import sys
from collections.abc import Sequence
from pathlib import Path
from subprocess import DEVNULL

import pytest

from landmass_emu.domain.match import MatchPlan
from landmass_emu.hosting.process import ProcessHostConfig, ProcessMatchHost
from landmass_emu.ports.match_host import GameEndpoint, MatchStartError

PLANO = MatchPlan(
    map_file="ONS-Treino",
    game_class="XGame.LM_DeathMatch",
    max_players=8,
    time_limit=10,
    goal_score=20,
)
DORME = [sys.executable, "-c", "import time; time.sleep(60)"]
LOG_PARTIDA = """\
GameEnded: XGame.LM_TeamGame Ended Deathmatch Exp/Money ==============================
GameEnded:     Player           = Tester2
GameEnded:     Reason           = TimeLimit
GameEnded:     Ranking          = 1
GameEnded:     Kills            = 0
GameEnded:     Played           = 100.00%
GameEnded:     TotalExp         = 0
GameEnded:     TotalMoney       = 0
GameEnded: ==============================================================
"""


def _config(
    tmp_path: Path, port_min: int, port_max: int, timeout: float = 5.0
) -> ProcessHostConfig:
    return ProcessHostConfig(
        server_dir=tmp_path,
        game_host="127.0.0.1",
        port_min=port_min,
        port_max=port_max,
        ready_timeout=timeout,
        message_addr="127.0.0.1:7313",
        version=1,
        login_num="teste",
    )


class _Falso:
    """No lugar de `LandMass.exe`: um processo Python com `argv`. O `netstat` anuncia a porta e o
    PID do último processo lançado, como o servidor real faria quando abre a porta."""

    def __init__(self, *, anuncia: bool = True, argv: Sequence[str] = DORME) -> None:
        self.portas: list[int] = []
        self.processos: list[asyncio.subprocess.Process] = []
        self.logs: list[str] = []
        self._anuncia = anuncia
        self._argv = list(argv)

    def argv(self, plan: MatchPlan, port: int, log_name: str) -> list[str]:
        self.portas.append(port)
        self.logs.append(log_name)
        return self._argv

    async def spawn(self, argv: list[str], cwd: Path) -> asyncio.subprocess.Process:
        proc = await asyncio.create_subprocess_exec(
            *argv, cwd=cwd, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL
        )
        self.processos.append(proc)
        return proc

    async def netstat(self) -> str:
        if not self._anuncia or not self.processos:
            return ""
        return f"  UDP    0.0.0.0:{self.portas[-1]}    *:*    {self.processos[-1].pid}\n"


def _host(tmp_path: Path, falso: _Falso, timeout: float = 5.0) -> ProcessMatchHost:
    return ProcessMatchHost(
        _config(tmp_path, 48200, 48219, timeout),
        spawn=falso.spawn,
        netstat=falso.netstat,
        argv=falso.argv,
    )


async def _sem_queda() -> None:
    return None


async def test_pronto_quando_a_porta_aparece_com_o_pid_do_processo(tmp_path: Path) -> None:
    falso = _Falso()
    host = _host(tmp_path, falso)
    try:
        endereco = await host.start(7, PLANO, _sem_queda)

        assert endereco == GameEndpoint("127.0.0.1", falso.portas[-1])
        assert 48200 <= endereco.port <= 48219
        assert falso.processos[-1].returncode is None
    finally:
        await host.close()


async def test_finish_encerra_o_processo_e_nao_dispara_a_queda(tmp_path: Path) -> None:
    falso = _Falso()
    host = _host(tmp_path, falso)
    quedas: list[int] = []

    async def ao_cair() -> None:
        quedas.append(1)

    await host.start(7, PLANO, ao_cair)
    host.finish(7)
    await asyncio.wait_for(falso.processos[-1].wait(), 5)
    await asyncio.sleep(0.2)

    assert falso.processos[-1].returncode is not None
    assert quedas == []


async def test_porta_que_nao_aparece_na_tabela_falha_no_prazo(tmp_path: Path) -> None:
    falso = _Falso(anuncia=False)
    host = _host(tmp_path, falso, timeout=0.3)

    with pytest.raises(MatchStartError, match="não abriu a porta"):
        await host.start(7, PLANO, _sem_queda)
    await asyncio.wait_for(falso.processos[-1].wait(), 5)
    assert falso.processos[-1].returncode is not None


async def test_processo_que_morre_antes_de_abrir_a_porta_falha_logo(tmp_path: Path) -> None:
    falso = _Falso(anuncia=False, argv=[sys.executable, "-c", "raise SystemExit(3)"])
    host = _host(tmp_path, falso)

    with pytest.raises(MatchStartError, match="encerrou antes"):
        await host.start(7, PLANO, _sem_queda)


async def test_queda_depois_de_pronto_chama_on_exit(tmp_path: Path) -> None:
    falso = _Falso(argv=[sys.executable, "-c", "import time; time.sleep(0.5)"])
    host = _host(tmp_path, falso)
    caiu = asyncio.Event()

    async def ao_cair() -> None:
        caiu.set()

    try:
        await host.start(7, PLANO, ao_cair)
        await asyncio.wait_for(caiu.wait(), 10)
    finally:
        await host.close()


async def test_sem_porta_livre_na_faixa_falha_antes_de_lancar(tmp_path: Path) -> None:
    ocupada = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ocupada.bind(("0.0.0.0", 48230))
    falso = _Falso()
    host = ProcessMatchHost(
        _config(tmp_path, 48230, 48230), spawn=falso.spawn, netstat=falso.netstat, argv=falso.argv
    )
    try:
        with pytest.raises(MatchStartError, match="nenhuma porta UDP livre"):
            await host.start(7, PLANO, _sem_queda)
        assert falso.processos == []
    finally:
        ocupada.close()


async def test_executavel_inexistente_vira_erro_de_inicio(tmp_path: Path) -> None:
    ausente = [str(tmp_path / "nao_existe.exe")]
    host = ProcessMatchHost(
        _config(tmp_path, 48200, 48219),
        argv=lambda plano, porta, nome: ausente,
        netstat=_sem_tabela,
    )

    with pytest.raises(MatchStartError, match="não iniciou"):
        await host.start(7, PLANO, _sem_queda)


async def _sem_tabela() -> str:
    return ""


async def test_end_sem_janela_derruba_o_processo_e_le_o_bloco_do_log(tmp_path: Path) -> None:
    falso = _Falso()
    host = ProcessMatchHost(
        _config(tmp_path, 48200, 48219),
        spawn=falso.spawn,
        netstat=falso.netstat,
        argv=falso.argv,
        exit_sender=lambda pid: False,
    )
    await host.start(7, PLANO, _sem_queda)
    (tmp_path / falso.logs[-1]).write_text(LOG_PARTIDA, encoding="utf-8")

    jogadores = await host.end(7)

    assert [j.nickname for j in jogadores] == ["Tester2"]
    assert falso.processos[-1].returncode is not None


async def test_end_digita_exit_e_espera_o_motor_sair(tmp_path: Path) -> None:
    falso = _Falso()
    pedidos: list[int] = []

    def digita_exit(pid: int) -> bool:
        # No lugar do motor: o processo de teste grava o log e sai ao receber o `exit`.
        pedidos.append(pid)
        (tmp_path / falso.logs[-1]).write_text(LOG_PARTIDA, encoding="utf-8")
        falso.processos[-1].kill()
        return True

    host = ProcessMatchHost(
        _config(tmp_path, 48200, 48219),
        spawn=falso.spawn,
        netstat=falso.netstat,
        argv=falso.argv,
        exit_sender=digita_exit,
    )
    await host.start(7, PLANO, _sem_queda)

    jogadores = await host.end(7)

    assert pedidos == [falso.processos[-1].pid]
    assert [j.nickname for j in jogadores] == ["Tester2"]


async def test_end_sem_servidor_devolve_vazio(tmp_path: Path) -> None:
    host = ProcessMatchHost(_config(tmp_path, 48200, 48219), exit_sender=lambda pid: False)

    assert await host.end(99) == ()
