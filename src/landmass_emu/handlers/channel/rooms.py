"""Salas: 301 criar, 311 entrar, 321 sair, 401 pronto e início, 420 slot, 700 expulsar.

Regras em `domain/rooms.py`; layouts em `protocol/channel.py`; evidências em `re/rooms.md`.
Difusão: `lobby.broadcast` para o que o cliente aplica no canal inteiro (302 na criação, 312, 322,
332, 342, 412); `lobby.send_to` para quem está na sala (402, 403, 421). Entrar na sala não tira o
jogador do lobby: continua recebendo a lista e o chat do canal.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.rooms import Room, RoomError, RoomReason, Rooms
from landmass_emu.handlers.channel.records import ChannelRecords
from landmass_emu.net.server import Reply, reply_body
from landmass_emu.net.session import Session
from landmass_emu.protocol.channel import (
    ROOM_SLOTS,
    CsChangeRoomMasterOut,
    CsChangeRoomSlotIn,
    CsChangeRoomSlotOut,
    CsCreateRoomIn,
    CsCreateRoomOut,
    CsErrorEnvelope,
    CsExpelPlayerIn,
    CsExpelPlayerOut,
    CsInRoomError,
    CsInRoomIn,
    CsInRoomOut,
    CsOp,
    CsOutRoomOut,
    CsReadyGameIn,
    CsReadyGameOut,
    CsRemoveRoomOut,
    CsRoomInfoOut,
    CsRoomStateOut,
    CsStartGameOut,
)
from landmass_emu.protocol.header import CHANNEL_NET_CODE
from landmass_emu.sniffer import hexdump

log = logging.getLogger(__name__)

# Códigos do envelope (chave de `msg_error` no landmass.wdb, verificada no arquivo do cliente).
ERR_CREATE_NAME_SHORT = 211000202  # "O nome da sala deve ter no mínimo 3 caracteres." (302)
ERR_CREATE = 211000201  # "Não pode criar Sala. Tente novamente." (302)
ERR_NOT_READY = 241002702  # "Ninguem está pronto nesta sala." (404)
ERR_NOT_OWNER = 241000302  # "%p não é o líder da sala." (701)
ERR_NOT_IN_ROOM = 241001202  # "Este jogador não encontra-se na sala." (701)

# Código de erro do 312 (short). O cliente monta a mensagem por `FUN_10021c80` (gap no RE); o
# número é o sufixo de 211000000 + código em `msg_error`.
JOIN_CODES: dict[RoomReason, int] = {
    RoomReason.NOT_FOUND: 1001,  # 211001001 "Esta sala não existe"
    RoomReason.FULL: 1202,  # 211001202 "Sala está cheia"
    RoomReason.WRONG_PASSWORD: 1701,  # 211001701 "Senha inválida"
    # shortcut: 212000200 "partida já iniciada" tem prefixo 212, que o short não carrega; revisar.
    RoomReason.STARTED: 200,
}


@dataclass(frozen=True, slots=True)
class GameEndpoint:
    """Endereço da partida no 403 (`LANDMASS_GAME_HOST` e `LANDMASS_GAME_PORT`)."""

    host: str
    port: int


class RoomHandlers:
    def __init__(
        self, lobby: Lobby, rooms: Rooms, records: ChannelRecords, game: GameEndpoint
    ) -> None:
        self._lobby = lobby
        self._rooms = rooms
        self._records = records
        self._game = game

    async def create_room(self, session: Session, payload: bytes) -> Sequence[Reply]:
        guid = self._lobby.guid_of(session)
        if guid is None:
            log.warning("[%s] CreateRoom fora do lobby; ignorado", session.peer)
            return []
        log.info("[%s] CreateRoom\n%s", session.peer, hexdump(payload))
        req = CsCreateRoomIn.unpack(payload)
        try:
            # shortcut: valores fora da faixa são limitados e logados, não recusados: um offset
            # inferido errado não pode impedir toda criação em silêncio.
            room = self._rooms.create(
                guid,
                name=req.name,
                password=req.password,
                scale=self._clamp(req.scale, 0, 255),
                game_mode=self._clamp(req.game_mode, 0, 255),
                map_num=self._clamp(req.map_num, 0, 32767),
                max_player=self._clamp(req.max_player, 1, ROOM_SLOTS),
                team_count=self._clamp(req.team_count, 0, 255),
                limit_time=self._clamp(req.limit_time, 0, 255),
                limit_score=self._clamp(req.limit_score, 0, 32767),
            )
        except RoomError as e:
            log.info("[%s] CreateRoom recusado: %s", session.peer, e.reason.value)
            code = ERR_CREATE_NAME_SHORT if e.reason is RoomReason.BAD_NAME else ERR_CREATE
            return [CsErrorEnvelope(CsOp.CREATE_ROOM_OUT, code)]
        snapshot = self._records.room(room)
        log.info("[%s] sala %d criada: %s", session.peer, room.room_id, room.name)
        # Ordem: 302 cria o nó em todo o lobby; 312 põe o criador no slot 0 (+0xa4 e contagem);
        # 314 e 317 vão só a ele, que refaz slots e estado da sala.
        self._to_lobby(CsCreateRoomOut(snapshot))
        self._to_lobby(CsInRoomOut(room.room_id, guid, 0))
        return [CsRoomInfoOut(snapshot), self._records.room_players(room)]

    async def in_room(self, session: Session, payload: bytes) -> Sequence[Reply]:
        guid = self._lobby.guid_of(session)
        if guid is None:
            log.warning("[%s] InRoom fora do lobby; ignorado", session.peer)
            return []
        log.info("[%s] InRoom\n%s", session.peer, hexdump(payload))
        req = CsInRoomIn.unpack(payload)
        try:
            room = self._rooms.join(req.room_id, guid, req.password)
        except RoomError as e:
            code = JOIN_CODES.get(e.reason)
            if code is None:
                log.info("[%s] InRoom ignorado: %s", session.peer, e.reason.value)
                return []
            log.info(
                "[%s] InRoom recusado na sala %d: %s", session.peer, req.room_id, e.reason.value
            )
            target = self._rooms.get(req.room_id)
            snap = None if target is None else self._records.room(target)
            return [CsInRoomError(code, req.room_id, snap)]
        snapshot = self._records.room(room)
        slot = room.members[guid].slot
        log.info("[%s] entrou na sala %d no slot %d", session.peer, room.room_id, slot)
        # 312 vai ao canal: o cliente põe o jogador na sala e soma no contador de todos.
        self._to_lobby(CsInRoomOut(room.room_id, guid, slot))
        return [CsRoomInfoOut(snapshot), self._records.room_players(room)]

    def leave(self, guid: int) -> None:
        """Tira o jogador da sala, se houver, e avisa o canal: 322 sempre; 332 se trocou o dono; 342
        se a sala ficou vazia e foi removida."""
        result = self._rooms.leave(guid)
        if result is None:
            return
        room_id = result.room.room_id
        self._to_lobby(CsOutRoomOut(room_id, guid))
        if result.removed:
            log.info("sala %d removida: sem jogadores", room_id)
            self._to_lobby(CsRemoveRoomOut(room_id))
        elif result.new_master is not None:
            log.info("sala %d: novo dono %d", room_id, result.new_master)
            self._to_lobby(CsChangeRoomMasterOut(room_id, result.new_master))

    async def out_room(self, session: Session, payload: bytes) -> Sequence[Reply]:
        guid = self._lobby.guid_of(session)
        if guid is not None:
            self.leave(guid)
        return []

    async def ready_game(self, session: Session, payload: bytes) -> Sequence[Reply]:
        """401: o dono inicia (403) quando os outros estão prontos; os demais alternam (402)."""
        guid = self._lobby.guid_of(session)
        if guid is None:
            return []
        req = CsReadyGameIn.unpack(payload)
        room = self._rooms.room_of(guid)
        if room is None:
            log.info("[%s] ReadyGame fora de sala; ignorado", session.peer)
            return []
        if room.master == guid:
            try:
                started = self._rooms.start(guid, req.morats)
            except RoomError as e:
                log.info("[%s] início recusado: %s", session.peer, e.reason.value)
                if e.reason is RoomReason.NOT_READY:
                    return [CsErrorEnvelope(CsOp.READY_GAME_ERROR, ERR_NOT_READY)]
                return []
            log.info("[%s] partida iniciada na sala %d", session.peer, started.room_id)
            self._to_lobby(CsRoomStateOut(started.room_id, started.state))
            self._to_room(started, CsStartGameOut(self._game.host, self._game.port))
            return []
        try:
            room, ready = self._rooms.toggle_ready(guid, req.morats)
        except RoomError as e:
            log.info("[%s] pronto recusado: %s", session.peer, e.reason.value)
            return []
        self._to_room(room, CsReadyGameOut(guid, ready, req.morats))
        return []

    async def change_room_slot(self, session: Session, payload: bytes) -> Sequence[Reply]:
        guid = self._lobby.guid_of(session)
        if guid is None:
            return []
        req = CsChangeRoomSlotIn.unpack(payload)
        try:
            room = self._rooms.change_slot(guid, req.slot)
        except RoomError as e:
            log.info("[%s] troca de slot recusada: %s", session.peer, e.reason.value)
            return []
        self._to_room(room, CsChangeRoomSlotOut(guid, req.slot))
        return []

    async def expel_player(self, session: Session, payload: bytes) -> Sequence[Reply]:
        guid = self._lobby.guid_of(session)
        if guid is None:
            return []
        req = CsExpelPlayerIn.unpack(payload)
        try:
            expelled = self._rooms.expel(guid, req.position)
        except RoomError as e:
            log.info("[%s] expulsão recusada: %s", session.peer, e.reason.value)
            code = ERR_NOT_OWNER if e.reason is RoomReason.NOT_OWNER else ERR_NOT_IN_ROOM
            return [CsErrorEnvelope(CsOp.EXPEL_PLAYER_OUT, code)]
        log.info("[%s] expulsou %d da sala %d", session.peer, expelled.guid, expelled.room.room_id)
        self._to_lobby(CsOutRoomOut(expelled.room.room_id, expelled.guid))
        return [CsExpelPlayerOut(0)]

    @staticmethod
    def _clamp(value: int, low: int, high: int) -> int:
        return min(max(value, low), high)

    def _to_lobby(self, reply: Reply) -> None:
        self._lobby.broadcast(reply_body(reply, CHANNEL_NET_CODE))

    def _to_room(self, room: Room, reply: Reply) -> None:
        self._lobby.send_to(room.members, reply_body(reply, CHANNEL_NET_CODE))
