"""Chat do lobby: 240 SendMsg do cliente; 241 vai a todos do lobby, remetente incluído."""

import logging
from collections.abc import Sequence

from landmass_emu.domain.lobby import Lobby
from landmass_emu.net.server import Reply, reply_body
from landmass_emu.net.session import Session
from landmass_emu.protocol.channel import CsSendMessageIn, CsSendMessageOut
from landmass_emu.protocol.header import CHANNEL_NET_CODE

log = logging.getLogger(__name__)


async def send_message(lobby: Lobby, session: Session, payload: bytes) -> Sequence[Reply]:
    sender = lobby.guid_of(session)
    if sender is None:
        log.warning("[%s] SendMsg fora do lobby; ignorado", session.peer)
        return []
    req = CsSendMessageIn.unpack(payload)
    lobby.broadcast(reply_body(CsSendMessageOut(sender, req.msg_type, req.text), CHANNEL_NET_CODE))
    return []
