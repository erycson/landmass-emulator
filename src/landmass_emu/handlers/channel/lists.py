"""Listas sob pedido: 546 (jogadores, resposta 548) e 545 (salas, resposta 547).

Só responde a quem está no lobby. Pedido sem nenhum item conhecido não gera resposta.
"""

from collections.abc import Sequence

from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.rooms import Rooms
from landmass_emu.handlers.channel.records import ChannelRecords
from landmass_emu.net.server import Reply
from landmass_emu.net.session import Session
from landmass_emu.protocol.channel import (
    CsPlayerProperty,
    CsRefreshPlayerListIn,
    CsRefreshPlayerListOut,
    CsRefreshRoomListIn,
    CsRefreshRoomListOut,
)


class ListHandlers:
    def __init__(self, lobby: Lobby, rooms: Rooms, records: ChannelRecords) -> None:
        self._lobby = lobby
        self._rooms = rooms
        self._records = records

    async def refresh_player_list(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if self._lobby.guid_of(session) is None:
            return []
        req = CsRefreshPlayerListIn.unpack(payload)
        # shortcut: clã e nest saem zerados (o lobby guarda só nick e exp).
        found = tuple(
            CsPlayerProperty(client_guid=g, total_exp=self._lobby.exp_of(g))
            for g in req.client_guids
            if self._lobby.is_member(g)
        )
        if not found:
            return []
        return [CsRefreshPlayerListOut(found)]

    async def refresh_room_list(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if self._lobby.guid_of(session) is None:
            return []
        req = CsRefreshRoomListIn.unpack(payload)
        rooms = (self._rooms.get(g) for g in req.room_guids)
        found = tuple(self._records.room(r) for r in rooms if r is not None)
        if not found:
            return []
        return [CsRefreshRoomListOut(found)]
