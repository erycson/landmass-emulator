"""Progressão no canal: tutorial (600 → 601), registro do jogador no login (101) e saldos (900,
902). O estado é lido do banco a cada pedido (07-progression §2.5)."""

import logging
from collections.abc import Sequence

from landmass_emu.domain.progression import Progression, ProgressionService
from landmass_emu.net.server import Reply
from landmass_emu.net.session import Session
from landmass_emu.ports.progression import ProgressionRepository
from landmass_emu.protocol.progression import (
    CsChargeCashOut,
    CsChargePointOut,
    CsTutorialClearIn,
    CsTutorialClearOut,
    PlayerRecord,
)

log = logging.getLogger(__name__)


class ProgressionHandlers:
    def __init__(self, progression: ProgressionRepository, rules: ProgressionService) -> None:
        self._progression = progression
        self._rules = rules

    async def tutorial_clear(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if session.account is None:
            log.warning("[%s] ClearTutorial antes do login; ignorado", session.peer)
            return []
        # Passo fora de 0 a 2 levanta ValueError; o roteador loga e ignora, sem gravar.
        bit = self._rules.tutorial_bit(CsTutorialClearIn.unpack(payload).step)
        progress = await self._progression.mark_tutorial(session.account.id, bit)
        return [CsTutorialClearOut(tutorial_clear=progress.tutorial_clear, point=progress.ld)]

    async def login_state(self, account_id: int) -> tuple[PlayerRecord, Sequence[Reply]]:
        """Registro do 101 e os pushes de saldo. Os pushes vêm depois do 111: o nó do jogador já
        existe e o cliente já montou a tela."""
        progress = await self._progression.get(account_id)
        return self.record_of(progress), (
            CsChargeCashOut(cash=progress.cash),
            CsChargePointOut(point=progress.ld),
        )

    async def total_exp(self, account_id: int) -> int:
        """Exp do jogador que entra no lobby. O 121 sobrescreve o nó do próprio jogador (`@4` →
        +0x3c, tools/re/LM_Engine.dll/channel_dispatch_FUN_1001da60.c L2772–2824), então o 121
        precisa
        levar a exp real (`CsChannelPlayer.total_exp`)."""
        return (await self._progression.get(account_id)).total_exp

    @staticmethod
    def record_of(progress: Progression) -> PlayerRecord:
        return PlayerRecord(
            tutorial_clear=progress.tutorial_clear,
            total_exp=progress.total_exp,
            cash=progress.cash,
            point=progress.ld,
        )
