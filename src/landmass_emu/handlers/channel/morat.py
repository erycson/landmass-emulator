"""Morat regular: 105 SetRegular grava nest e classe da conta; responde 104 (corpo vazio)."""

import logging
from collections.abc import Sequence

from landmass_emu.domain.regular import RegularService
from landmass_emu.net.server import Reply
from landmass_emu.net.session import Session
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.protocol.inventory import CsSetRegularIn, CsSetRegularOut

log = logging.getLogger(__name__)


class MoratHandlers:
    def __init__(self, accounts: AccountRepository, regular: RegularService) -> None:
        self._accounts = accounts
        self._regular = regular

    async def set_regular(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if session.account is None:
            log.warning("[%s] SetRegular antes do login; ignorado", session.peer)
            return []
        # Payload curto (struct.error) e faixa inválida (ValueError) saem antes de gravar.
        req = CsSetRegularIn.unpack(payload)
        choice = self._regular.choose(req.nest, req.morat_class)
        await self._accounts.set_regular(session.account.id, choice.nest, choice.morat_class)
        log.info("[%s] regular: nest %d, classe %d", session.peer, choice.nest, choice.morat_class)
        return [CsSetRegularOut()]
