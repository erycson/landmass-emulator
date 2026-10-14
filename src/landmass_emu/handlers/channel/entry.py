"""Lobby: 100/101 (login no canal), 120/121 (entra), 122/123 (sai) e queda da conexão."""

import logging
from collections.abc import Sequence
from dataclasses import replace

from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.rooms import Rooms
from landmass_emu.handlers.channel.progression import ProgressionHandlers
from landmass_emu.handlers.channel.records import ChannelRecords
from landmass_emu.handlers.channel.rooms import RoomHandlers
from landmass_emu.net.server import Reply, reply_body
from landmass_emu.net.session import Session
from landmass_emu.ports.session_keys import SessionKeyRegistry
from landmass_emu.protocol.channel import (
    MAX_LOBBY_ENTRIES,
    CsChannelInfoOut,
    CsChannelPlayer,
    CsChannelPlayerInfoOut,
    CsChannelRoomInfoOut,
    CsInChannelOut,
    CsInChannelServerIn,
    CsInChannelServerOut,
    CsOutChannelOut,
)
from landmass_emu.protocol.header import CHANNEL_NET_CODE
from landmass_emu.sniffer import hexdump

log = logging.getLogger(__name__)

RESULT_OK = 0
# shortcut: -160 (INVALID_PASSWORD do Message) para chave recusada; o canal original pode usar
# outro código. Confirmar no cliente real.
RESULT_INVALID_LOGIN = -160


class EntryHandlers:
    def __init__(
        self,
        sessions: SessionKeyRegistry,
        lobby: Lobby,
        rooms: Rooms,
        records: ChannelRecords,
        room_handlers: RoomHandlers,
        progression: ProgressionHandlers,
    ) -> None:
        self._sessions = sessions
        self._lobby = lobby
        self._rooms = rooms
        self._records = records
        self._room_handlers = room_handlers
        self._progression = progression

    async def in_channel_server(self, session: Session, payload: bytes) -> Sequence[Reply]:
        req = CsInChannelServerIn.unpack(payload)
        session.account = None
        account = self._sessions.resolve(req.session_key)
        if account is None:
            log.info("[%s] canal: login recusado\n%s", session.peer, hexdump(payload))
            return [CsInChannelServerOut(client_guid=0, result=RESULT_INVALID_LOGIN)]
        session.account = account
        log.info("[%s] canal: login de %s", session.peer, account.username)
        record, pushes = await self._progression.login_state(account.id)
        # ucAccess vai no @0x11 do 101 (valor+0x11): o cliente copia o registro para o próprio nó.
        record = replace(record, access=account.access_level)
        return [
            CsInChannelServerOut(client_guid=account.id, result=RESULT_OK, progress=record),
            CsChannelInfoOut(),
            *pushes,
        ]

    async def in_channel(self, session: Session, payload: bytes) -> Sequence[Reply]:
        # shortcut: payload (u32 num, ou vazio) ignorado porque o servidor tem um canal só; revisar
        # se o cliente real escolher canal por índice (a lista de 111 teria de ter mais entradas).
        account = session.account
        if account is None:
            log.warning("[%s] InChannel antes do login; ignorado", session.peer)
            return []
        # A exp do banco fica no lobby (151, 317, 548 e 549 a leem) e vai no 121 e no 101.
        exp = await self._progression.total_exp(account.id)
        # Entra antes de montar a lista: a 151 traz o próprio jogador (ver ChannelRecords).
        self._lobby.join(account.id, session, account.nickname, exp, account.access_level)
        me = CsChannelPlayer(
            client_guid=account.id,
            nick=account.nickname,
            total_exp=exp,
            access=account.access_level,
        )
        players = self._records.lobby_players()
        self._lobby.broadcast(reply_body(CsInChannelOut(me), CHANNEL_NET_CODE), exclude=session)
        log.info("[%s] entrou no lobby (%d jogadores)", session.peer, len(players))
        return [
            CsChannelPlayerInfoOut(players[:MAX_LOBBY_ENTRIES]),
            CsChannelRoomInfoOut(tuple(self._records.room(r) for r in self._rooms.all())),
            CsInChannelOut(me),
        ]

    async def out_channel(self, session: Session, payload: bytes) -> Sequence[Reply]:
        guid = self._lobby.guid_of(session)
        if guid is None:
            return []
        self._room_handlers.leave(guid)
        self._lobby.leave(session)
        self._lobby.broadcast(reply_body(CsOutChannelOut(guid), CHANNEL_NET_CODE))
        return [CsOutChannelOut(guid)]

    def disconnect(self, session: Session) -> None:
        guid = self._lobby.guid_of(session)
        if guid is None:
            return
        self._room_handlers.leave(guid)
        self._lobby.leave(session)
        log.info("[%s] saiu do lobby por queda da conexão", session.peer)
        self._lobby.broadcast(reply_body(CsOutChannelOut(guid), CHANNEL_NET_CODE))
