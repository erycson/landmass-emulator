"""Desligamento gracioso (D202).

O pedido vem de SIGINT ou SIGTERM, ou do arquivo de controle (D203). Quem está conectado recebe
avisos nos instantes de `shutdown_notice_seconds` antes do prazo. Na janela de recusa, que é o
maior aviso antes do prazo, o servidor não aceita conexões novas nem cria salas e partidas. No
prazo, as partidas em andamento são encerradas e gravadas com `server_shutdown`. O processo sai
antes do prazo só quando o lobby esvazia. Um pedido seguinte encurta o prazo; nunca o estende.
"""

import asyncio
import logging
import math
import signal
import time
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any, Protocol

from landmass_emu.control import take_request

log = logging.getLogger(__name__)

DEFAULT_NOTICE = "O servidor será desligado."


class ShutdownPort(Protocol):
    """O que o desligamento usa do canal. Montado em `app.py` com os componentes reais."""

    def notify(self, text: str) -> None: ...

    def players(self) -> int: ...

    async def end_matches(self) -> None: ...


def format_remaining(seconds: float) -> str:
    """Tempo que falta, arredondado para cima: 299,2 s vira "5 min"; 9,9 s vira "10 s"."""
    s = math.ceil(max(seconds, 0.0))
    if s >= 60:
        return f"{math.ceil(s / 60)} min"
    return f"{s} s"


def notice_text(message: str, remaining: float) -> str:
    base = message.strip() or DEFAULT_NOTICE
    return f"{base} Desligamento em {format_remaining(remaining)}."


class Shutdown:
    def __init__(
        self, leads: Sequence[int] = (), clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._leads = tuple(leads)  # segundos antes do prazo em que avisar
        self._clock = clock
        self._deadline: float | None = None
        self._message = ""
        self._port: ShutdownPort | None = None
        self._requested = asyncio.Event()

    def accepting(self) -> bool:
        """Verdadeiro até a janela de recusa, que é o maior aviso antes do prazo. Sem avisos, a
        janela é o próprio pedido. Dentro dela, conexões novas, salas e partidas são recusadas."""
        if self._deadline is None:
            return True
        return bool(self._leads) and self._restante() > max(self._leads)

    def attach(self, port: ShutdownPort) -> None:
        self._port = port

    def begin(self, after: float, message: str = "") -> None:
        """Pede a saída em `after` segundos. Pedido seguinte só encurta o prazo, e a mensagem mais
        recente que não vem vazia é a que vale."""
        deadline = self._clock() + max(after, 0.0)
        if self._deadline is None or deadline < self._deadline:
            self._deadline = deadline
        if message:
            self._message = message
        log.info("desligamento pedido: saída em %s", format_remaining(self._restante()))
        self._requested.set()

    async def run(
        self, *, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep, poll: float = 0.5
    ) -> None:
        """Espera o pedido e o conduz até o prazo ou o lobby vazio. Depois, encerra as partidas."""
        await self._requested.wait()
        port = self._port
        if port is None:
            raise RuntimeError("Shutdown sem porta: chame attach antes de run")
        enviados = self._avisa(port, frozenset())
        while self._restante() > 0 and port.players() > 0:
            restante = self._restante()
            if any(lead not in enviados and restante <= lead for lead in self._leads):
                enviados = self._avisa(port, enviados)
            await sleep(min(poll, restante))
        log.info("desligamento: encerrando partidas e saindo")
        await port.end_matches()

    def _restante(self) -> float:
        if self._deadline is None:
            return math.inf
        return max(self._deadline - self._clock(), 0.0)

    def _avisa(self, port: ShutdownPort, enviados: frozenset[int]) -> frozenset[int]:
        """Um aviso com o tempo que falta. Cobre também os instantes já passados, para não avisar
        de novo o que a mensagem atual já diz."""
        restante = self._restante()
        port.notify(notice_text(self._message, restante))
        return enviados | {lead for lead in self._leads if lead >= restante}


async def watch_control(path: Path, shutdown: Shutdown, interval: float = 1.0) -> None:
    """Lê o arquivo de controle a cada `interval` segundos. Roda até ser cancelado."""
    while True:
        pedido = take_request(path)
        if pedido is not None:
            shutdown.begin(pedido.at - time.time(), pedido.message)
        await asyncio.sleep(interval)


def install_signals(shutdown: Shutdown, grace: float) -> Callable[[], None]:
    """SIGINT e SIGTERM pedem o desligamento com o prazo `grace`. No Windows, SIGINT é Ctrl+C e
    SIGBREAK é Ctrl+Break; fechar a janela do console não chega como sinal e não tem tratamento.
    Um segundo sinal encerra já. Devolve a função que restaura os tratadores anteriores."""
    loop = asyncio.get_running_loop()
    recebidos = 0

    def ao_sinal(signum: int, frame: object) -> None:
        nonlocal recebidos
        recebidos += 1
        apos = grace if recebidos == 1 else 0.0
        loop.call_soon_threadsafe(shutdown.begin, apos)

    anteriores: dict[int, Any] = {}
    for nome in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sinal = getattr(signal, nome, None)
        if sinal is not None:
            anteriores[sinal] = signal.signal(sinal, ao_sinal)

    def restaura() -> None:
        for sinal, antigo in anteriores.items():
            signal.signal(sinal, antigo)

    return restaura
