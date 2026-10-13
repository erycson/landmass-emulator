"""Lobby: 100/101 (login no canal), 120/121 (entra), 122/123 (sai) e queda da conexão."""

import logging
from collections.abc import Sequence

from landmass_emu.domain.lobby import Lobby
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


async def in_channel_server(
    sessions: SessionKeyRegistry, session: Session, payload: bytes
) -> Sequence[Reply]:
    req = CsInChannelServerIn.unpack(payload)
    session.account = None
    account = sessions.resolve(req.session_key)
    if account is None:
        log.info("[%s] canal: login recusado\n%s", session.peer, hexdump(payload))
        return [CsInChannelServerOut(client_guid=0, result=RESULT_INVALID_LOGIN)]
    session.account = account
    log.info("[%s] canal: login de %s", session.peer, account.username)
    return [CsInChannelServerOut(client_guid=account.id, result=RESULT_OK), CsChannelInfoOut()]


async def in_channel(lobby: Lobby, session: Session, payload: bytes) -> Sequence[Reply]:
    # shortcut: payload (u32 num, ou vazio) ignorado porque o servidor tem um canal só; revisar se
    # o cliente real escolher canal por índice (a lista de 111 teria de ter mais entradas).
    if session.account is None:
        log.warning("[%s] InChannel antes do login; ignorado", session.peer)
        return []
    guid = session.account.id
    # Snapshot antes do join: quem entrou depois de este cliente enviar 100 chega via broadcast.
    others = tuple(CsChannelPlayer(client_guid=g) for g in lobby.guids() if g != guid)
    me = CsChannelPlayer(client_guid=guid)
    lobby.join(guid, session)
    lobby.broadcast(reply_body(CsInChannelOut(me), CHANNEL_NET_CODE), exclude=session)
    log.info("[%s] entrou no lobby (%d jogadores)", session.peer, len(others) + 1)
    return [
        CsChannelPlayerInfoOut(others[:MAX_LOBBY_ENTRIES]),
        CsChannelRoomInfoOut(),
        CsInChannelOut(me),
    ]


async def out_channel(lobby: Lobby, session: Session, payload: bytes) -> Sequence[Reply]:
    guid = lobby.leave(session)
    if guid is None:
        return []
    lobby.broadcast(reply_body(CsOutChannelOut(guid), CHANNEL_NET_CODE))
    return [CsOutChannelOut(guid)]


def disconnect(lobby: Lobby, session: Session) -> None:
    guid = lobby.leave(session)
    if guid is not None:
        log.info("[%s] saiu do lobby por queda da conexão", session.peer)
        lobby.broadcast(reply_body(CsOutChannelOut(guid), CHANNEL_NET_CODE))
