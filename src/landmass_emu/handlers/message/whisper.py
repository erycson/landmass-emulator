"""Sussurro (160): entrega ao destinatário conectado no Message (F12).

Destinatário fora do Message, ou que bloqueou o remetente, recebe `MsResult.CONTACT_OFFLINE`. Nick
inexistente recebe `MsResult.INVALID_VALUE`. Entrega com sucesso não responde ao remetente: o 161
vai só ao destinatário (inferido: o cliente não tem caso de confirmação).
"""

import logging
from collections.abc import Sequence

from landmass_emu.domain.presence import MessagePresence
from landmass_emu.net.server import Reply, reply_body
from landmass_emu.net.session import Session
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.social import Relation, SocialRepository
from landmass_emu.protocol.header import MESSAGE_NET_CODE
from landmass_emu.protocol.message import (
    MsResult,
    MsSendWhisperIn,
    MsWhisperErrorOut,
    MsWhisperOut,
)

log = logging.getLogger(__name__)


class WhisperHandlers:
    def __init__(
        self,
        accounts: AccountRepository,
        social: SocialRepository,
        presence: MessagePresence,
    ) -> None:
        self._accounts = accounts
        self._social = social
        self._presence = presence

    async def send_whisper(self, session: Session, payload: bytes) -> Sequence[Reply]:
        sender = session.account
        if sender is None:
            log.warning("[%s] SendWhisper antes do login; ignorado", session.peer)
            return []
        req = MsSendWhisperIn.unpack(payload)
        target = await self._accounts.find_by_nickname(req.target)
        if target is None:
            return [MsWhisperErrorOut(MsResult.INVALID_VALUE, req.target, req.text)]
        recipient = self._presence.recipient_of(target.id)
        if recipient is None or await self._social.has(Relation.BLOCK, target.id, sender.id):
            return [MsWhisperErrorOut(MsResult.CONTACT_OFFLINE, req.target, req.text)]
        recipient.send(reply_body(MsWhisperOut(sender.nickname, req.text), MESSAGE_NET_CODE))
        return []
