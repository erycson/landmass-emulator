"""Lançamento desligado: a partida é o endereço fixo das settings (`LANDMASS_GAME_HOST/PORT`).
Sem processo e sem espera: o 403 vai logo depois do 412, como antes do marco 4."""

from collections.abc import Awaitable, Callable

from landmass_emu.domain.match import MatchPlan
from landmass_emu.domain.match_stats import GameEndedPlayer
from landmass_emu.ports.match_host import GameEndpoint


class FixedMatchHost:
    def __init__(self, endpoint: GameEndpoint) -> None:
        self._endpoint = endpoint

    async def start(
        self, room_id: int, plan: MatchPlan, on_exit: Callable[[], Awaitable[None]]
    ) -> GameEndpoint:
        return self._endpoint

    def finish(self, room_id: int) -> None:
        return None

    async def end(self, room_id: int) -> tuple[GameEndedPlayer, ...]:
        return ()

    async def command(self, room_id: int, line: str) -> bool:
        return False

    async def close(self) -> None:
        return None
