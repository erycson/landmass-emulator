"""Chat: 240 SendMsg do cliente; 241 vai a todos do lobby, ou só a quem está na sala do
remetente. Remetente incluído. shortcut: o escopo do 240 é gap no RE (rooms.md §6); usar
a sala do remetente é a suposição. Revisar no cliente real.

Dentro da partida o cliente também manda o chat por aqui, com ` //GAMECHAT` no fim
(`SendMsgEx`, XInterface). O `/bot` do dono não volta à sala: segue à partida (D254)."""

import logging
from collections.abc import Sequence

from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.rooms import ROOM_PLAYING, Rooms
from landmass_emu.net.server import Reply, reply_body
from landmass_emu.net.session import Session
from landmass_emu.ports.match_host import MatchHost
from landmass_emu.protocol.channel import CsSendMessageIn, CsSendMessageOut
from landmass_emu.protocol.header import CHANNEL_NET_CODE

log = logging.getLogger(__name__)

GAMECHAT = b"//GAMECHAT"
BOT_COMMAND = b"/bot"


class ChatHandlers:
    def __init__(self, lobby: Lobby, rooms: Rooms, match: MatchHost) -> None:
        self._lobby = lobby
        self._rooms = rooms
        self._match = match

    async def send_message(self, session: Session, payload: bytes) -> Sequence[Reply]:
        sender = self._lobby.guid_of(session)
        if sender is None:
            log.warning("[%s] SendMsg fora do lobby; ignorado", session.peer)
            return []
        req = CsSendMessageIn.unpack(payload)
        room = self._rooms.room_of(sender)
        command = req.text.removesuffix(GAMECHAT).strip()
        if (
            room is not None
            and room.state == ROOM_PLAYING
            and room.master == sender
            and command.lower().startswith(BOT_COMMAND)
        ):
            line = command.decode("latin-1")
            ok = await self._match.command(room.room_id, line)
            log.info(
                "[%s] %s do dono na sala %d (tipo %d): %s",
                session.peer,
                line,
                room.room_id,
                req.msg_type,
                "repassado à partida" if ok else "partida sem canal de comandos",
            )
            return []
        body = reply_body(CsSendMessageOut(sender, req.msg_type, req.text), CHANNEL_NET_CODE)
        if room is None:
            self._lobby.broadcast(body)
        else:
            self._lobby.send_to(room.members, body)
        return []
