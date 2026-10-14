"""Portas da partida: quem hospeda o servidor de jogo e de onde vêm os dados do mapa.

Handlers do Channel dependem só disto. A implementação com processo fica em `hosting/`.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from landmass_emu.domain.match import MapRecord, MatchPlan


@dataclass(frozen=True, slots=True)
class GameEndpoint:
    """Endereço da partida no 403 (`NotifyStartGame`)."""

    host: str
    port: int


class MatchStartError(Exception):
    """A partida não pôde começar. O dono recebe o erro 241000201; a causa vai ao log."""


class MatchHost(Protocol):
    async def start(
        self, room_id: int, plan: MatchPlan, on_exit: Callable[[], Awaitable[None]]
    ) -> GameEndpoint:
        """Garante um servidor de partida para a sala e espera ele aceitar conexões. `on_exit` é
        aguardado se o processo cair sozinho depois de pronto; não roda quando `finish` o encerra.
        Falha de início levanta `MatchStartError`."""
        ...

    def finish(self, room_id: int) -> None:
        """Encerra o servidor da sala, se houver. Chamar sem partida é seguro."""
        ...

    async def close(self) -> None:
        """Encerra todos os servidores (desligamento do emulador)."""
        ...


class MapCatalog(Protocol):
    def get(self, record_id: int) -> MapRecord | None: ...
