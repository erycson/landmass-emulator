"""Chat: 240 SendMsg do cliente; 241 vai a todos do lobby, ou só a quem está na sala do
remetente. Remetente incluído. shortcut: o escopo do 240 é gap no RE (rooms.md §6); usar
a sala do remetente é a suposição. Revisar no cliente real."""

import logging
from collections.abc import Sequence

from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.rooms import Rooms
from landmass_emu.net.server import Reply, reply_body
from landmass_emu.net.session import Session
from landmass_emu.protocol.channel import CsSendMessageIn, CsSendMessageOut
from landmass_emu.protocol.header import CHANNEL_NET_CODE

log = logging.getLogger(__name__)


class ChatHandlers:
    def __init__(self, lobby: Lobby, rooms: Rooms) -> None:
        self._lobby = lobby
        self._rooms = rooms

    async def send_message(self, session: Session, payload: bytes) -> Sequence[Reply]:
        sender = self._lobby.guid_of(session)
        if sender is None:
            log.warning("[%s] SendMsg fora do lobby; ignorado", session.peer)
            return []
        req = CsSendMessageIn.unpack(payload)
        body = reply_body(CsSendMessageOut(sender, req.msg_type, req.text), CHANNEL_NET_CODE)
        room = self._rooms.room_of(sender)
        if room is None:
            self._lobby.broadcast(body)
        else:
            self._lobby.send_to(room.members, body)
        return []
