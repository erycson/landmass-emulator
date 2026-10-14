"""Salas: 301 criar, 311 entrar, 321 sair, 401 pronto e início, 411 configurar, 420 mudar grupo,
451 expulsar, 461 convidar e 471 responder ao convite.

Regras em `domain/rooms.py`; layouts em `protocol/channel.py`; evidências em `re/rooms.md` e
`re/protocol_full.md`. O 700 (`/EXPEL` do console) não é executado: ver `CsExpelPlayerIn`.
Difusão: `lobby.broadcast` para o que o cliente aplica no canal inteiro (302 na criação, 312, 322,
332, 342, 412). Na entrada, quem já está na sala recebe 549 e não 312 (ver `_joined`);
`lobby.send_to` para quem está na sala (402, 403, 421) e para o convidado (463).
"""

import asyncio
import logging
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from functools import partial
from uuid import uuid4

from landmass_emu.audit import EconomyAudit
from landmass_emu.domain.loadout import LoadoutMember, LoadoutService
from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.match import MatchPlan, build_plan
from landmass_emu.domain.match_stats import (
    GameEndedPlayer,
    MatchRecord,
    PlayerMatchStats,
    with_game_end,
    with_played,
)
from landmass_emu.domain.rooms import (
    ROOM_PLAYER_SLOTS,
    ROOM_PLAYING,
    ROOM_WAITING,
    Room,
    RoomError,
    RoomReason,
    Rooms,
)
from landmass_emu.handlers.channel.records import ChannelRecords
from landmass_emu.net.server import Reply, reply_body
from landmass_emu.net.session import Session
from landmass_emu.ports.match_host import MapCatalog, MatchHost, MatchStartError
from landmass_emu.ports.matches import MatchRepository
from landmass_emu.ports.progression import ProgressionRepository
from landmass_emu.protocol.channel import (
    ROOM_FLAG_LIMIT_PLAYER,
    ROOM_FLAG_LIMIT_SCORE,
    ROOM_FLAG_LIMIT_TIME,
    ROOM_FLAG_MAP,
    ROOM_FLAG_MODE,
    CsChangeRoomMasterOut,
    CsChangeRoomPropertyIn,
    CsChangeRoomPropertyOut,
    CsChangeRoomSlotIn,
    CsChangeRoomSlotOut,
    CsCreateRoomIn,
    CsCreateRoomOut,
    CsEnterHangarOut,
    CsErrorEnvelope,
    CsExitPlayOut,
    CsInRoomError,
    CsInRoomIn,
    CsInRoomOut,
    CsInviteResultOut,
    CsLeaveHangarOut,
    CsOp,
    CsOutRoomOut,
    CsReadyGameIn,
    CsReadyGameOut,
    CsRemoveRoomOut,
    CsRoomEntryOut,
    CsRoomExpelIn,
    CsRoomInfoOut,
    CsRoomInviteAnswerIn,
    CsRoomInviteIn,
    CsRoomInviteOut,
    CsStartGameOut,
)
from landmass_emu.protocol.header import CHANNEL_NET_CODE
from landmass_emu.protocol.progression import CsChargeCashOut, CsChargePointOut
from landmass_emu.sniffer import hexdump

log = logging.getLogger(__name__)

# Códigos do envelope (chave de `msg_error` no landmass.wdb, verificada no arquivo do cliente).
ERR_CREATE_NAME_SHORT = 211000202  # "O nome da sala deve ter no mínimo 3 caracteres." (302)
ERR_CREATE = 211000201  # "Não pode criar Sala. Tente novamente." (302)
ERR_NOT_READY = 241002702  # "Ninguem está pronto nesta sala." (404)
ERR_MATCH_START = 241000201  # "Não foi possível iniciar a partida. Tente novamente." (404)
# Motivo do fim no histórico (`matches.end_reason`).
END_EXIT_PLAY = "exit_play"  # todos saíram da partida (500)
END_SERVER_EXIT = "server_exit"  # o servidor de partida caiu depois de pronto
END_RETURN = "return_to_room"  # o último em jogo voltou à sala sem 500 (o cliente não manda)
END_SHUTDOWN = "server_shutdown"  # o desligamento encerrou a partida no prazo (D202)

# Código de erro do 312 (short). O cliente monta a mensagem por `FUN_10021c80` (gap no RE); o
# número é o sufixo de 211000000 + código em `msg_error` do `landmass.wdb`.
JOIN_CODES: dict[RoomReason, int] = {
    RoomReason.NOT_FOUND: 1001,  # 211001001 "Esta sala não existe"
    RoomReason.FULL: 1202,  # 211001202 "Sala está cheia"
    RoomReason.WRONG_PASSWORD: 1701,  # 211001701 "Senha inválida"
    # shortcut: 212000200 "partida já iniciada" tem prefixo 212, que o short não carrega; revisar.
    RoomReason.STARTED: 200,
}

# CERR de `Core.u` (re/layouts_f0.md §7.3) para a resposta 462 ao convite.
CERR_INVITE_ROOM_NOT_ADMIN = -4061  # quem não é dono: envelope, e o cliente não mostra nada
CERR_FIND_PLAYER = -2460  # convidado fora do canal
CERR_NOT_ROOM = -2408  # quem convida não está em sala
CERR_FULL_ROOM = -2406  # sala cheia
CERR_IN_ROOM = -2411  # convidado já está em sala (ou é o próprio dono)
CERR_CANNOT_INVITE = -2412  # partida já começou
INVITE_CODES: dict[RoomReason, int] = {
    RoomReason.NOT_OWNER: CERR_INVITE_ROOM_NOT_ADMIN,
    RoomReason.NOT_IN_ROOM: CERR_NOT_ROOM,
    RoomReason.FULL: CERR_FULL_ROOM,
    RoomReason.ALREADY_IN_ROOM: CERR_IN_ROOM,
    RoomReason.STARTED: CERR_CANNOT_INVITE,
}


def _clamp(value: int, low: int, high: int) -> int:
    return min(max(value, low), high)


def _settings(req: CsChangeRoomPropertyIn) -> dict[str, int]:
    """Campos de 411 que o bit de `flags` manda mudar, já limitados como na criação (301)."""
    flags = req.flags
    out: dict[str, int] = {}
    if flags & ROOM_FLAG_MAP:
        out["map_num"] = _clamp(req.map_num, 0, 32767)
    if flags & ROOM_FLAG_MODE:
        out["game_mode"] = _clamp(req.game_mode, 0, 255)
        out["team_count"] = _clamp(req.team_count, 0, 255)
    if flags & ROOM_FLAG_LIMIT_PLAYER:
        out["max_player"] = _clamp(req.max_player, 1, ROOM_PLAYER_SLOTS)
    if flags & ROOM_FLAG_LIMIT_TIME:
        out["limit_time"] = _clamp(req.limit_time, 0, 255)
    if flags & ROOM_FLAG_LIMIT_SCORE:
        out["limit_score"] = _clamp(req.limit_score, 0, 32767)
    return out


class RoomHandlers:
    def __init__(
        self,
        lobby: Lobby,
        rooms: Rooms,
        records: ChannelRecords,
        match: MatchHost,
        maps: MapCatalog,
        matches: MatchRepository | None,
        progression: ProgressionRepository | None = None,
        audit: EconomyAudit | None = None,
        loadout: LoadoutService | None = None,
        accepting_matches: Callable[[], bool] | None = None,
    ) -> None:
        self._lobby = lobby
        self._rooms = rooms
        self._records = records
        self._match = match
        self._maps = maps
        self._matches = matches
        self._progression = progression
        self._audit = audit
        self._loadout = loadout
        # Falso no desligamento: sala nova e início de partida são recusados (D202).
        self._accepting = accepting_matches or (lambda: True)
        # Histórico em curso por sala: quem jogou no início. O fim e o motivo vêm depois.
        self._open: dict[int, MatchRecord] = {}
        # Hora em que cada jogador saiu da partida (500, volta à sala ou saída), por sala.
        self._left: dict[int, dict[int, datetime]] = {}
        # Parada do servidor de cada sala que acabou, à espera do `_save` que lê o log da partida.
        self._logs: dict[int, asyncio.Task[tuple[GameEndedPlayer, ...]]] = {}
        # Gravações disparadas por `leave` (síncrono); guardadas para não serem coletadas.
        self._saves: set[asyncio.Task[None]] = set()

    async def create_room(self, session: Session, payload: bytes) -> Sequence[Reply]:
        guid = self._lobby.guid_of(session)
        if guid is None:
            log.warning("[%s] CreateRoom fora do lobby; ignorado", session.peer)
            return []
        if not self._accepting():
            log.info("[%s] CreateRoom recusado: desligamento em curso", session.peer)
            return [CsErrorEnvelope(CsOp.CREATE_ROOM_OUT, ERR_CREATE)]
        log.info("[%s] CreateRoom\n%s", session.peer, hexdump(payload))
        req = CsCreateRoomIn.unpack(payload)
        try:
            # shortcut: valores fora da faixa são limitados e logados, não recusados: um offset
            # inferido errado não pode impedir toda criação em silêncio.
            room = self._rooms.create(
                guid,
                name=req.name,
                password=req.password,
                scale=_clamp(req.scale, 0, 255),
                game_mode=_clamp(req.game_mode, 0, 255),
                map_num=_clamp(req.map_num, 0, 32767),
                max_player=_clamp(req.max_player, 1, ROOM_PLAYER_SLOTS),
                team_count=_clamp(req.team_count, 0, 255),
                limit_time=_clamp(req.limit_time, 0, 255),
                limit_score=_clamp(req.limit_score, 0, 32767),
            )
        except RoomError as e:
            log.info("[%s] CreateRoom recusado: %s", session.peer, e.reason.value)
            code = ERR_CREATE_NAME_SHORT if e.reason is RoomReason.BAD_NAME else ERR_CREATE
            return [CsErrorEnvelope(CsOp.CREATE_ROOM_OUT, code)]
        log.info("[%s] sala %d criada: %s", session.peer, room.room_id, room.name)
        # 302 cria o nó em todo o lobby; depois a entrada do criador (312, 314 e 317).
        self._to_lobby(CsCreateRoomOut(self._records.room(room)))
        return self._joined(room, guid)

    async def in_room(self, session: Session, payload: bytes) -> Sequence[Reply]:
        guid = self._lobby.guid_of(session)
        if guid is None:
            log.warning("[%s] InRoom fora do lobby; ignorado", session.peer)
            return []
        log.info("[%s] InRoom\n%s", session.peer, hexdump(payload))
        req = CsInRoomIn.unpack(payload)
        current = self._rooms.room_of(guid)
        if current is not None and current.room_id == req.room_id:
            # Volta à própria sala depois da partida. Quem está na sala saiu da partida: o cliente
            # não manda 500 quando a partida acaba no servidor. Com o último a voltar, a partida
            # acaba e a sala volta à espera antes das respostas abaixo (D48, D49).
            self._leave_game(guid)
            if current.match_over():
                record = self._end(current)
                if record is not None:
                    await self._save(record, END_RETURN)
            # O lobby já sabe da sala: só quem entra recebe a sala de novo (312, 314, 317).
            slot = current.members[guid].slot
            return [
                CsInRoomOut(current.room_id, guid, slot),
                CsRoomInfoOut(self._records.room(current)),
                self._records.room_players(current),
            ]
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
        log.info("[%s] entrou na sala %d", session.peer, room.room_id)
        return self._joined(room, guid)

    def _joined(self, room: Room, guid: int) -> Sequence[Reply]:
        """Entrada de `guid` na sala: 549 a quem já está nela; 312 ao lobby, menos a quem já está
        nela; 314 e 317 ao entrante.

        O 312 soma 1 no contador de jogadores de quem o recebe (`disp@2908-2912`), e o 549 também:
        mandar os dois a quem já está na sala contaria duas vezes. Por isso esses clientes recebem
        só o 549, que traz o nó e o slot do entrante.
        """
        others = [g for g in room.members if g != guid]
        entering = self._records.room_player(room, guid)
        self._lobby.send_to(others, reply_body(CsRoomEntryOut(entering), CHANNEL_NET_CODE))
        slot = room.members[guid].slot
        self._lobby.broadcast(
            reply_body(CsInRoomOut(room.room_id, guid, slot), CHANNEL_NET_CODE), skip=others
        )
        return [CsRoomInfoOut(self._records.room(room)), self._records.room_players(room)]

    def leave(self, guid: int) -> None:
        """Tira o jogador da sala, se houver, e avisa o canal: 322 sempre; 332 se trocou o dono; 342
        se a sala ficou vazia e foi removida."""
        self._leave_game(guid)
        result = self._rooms.leave(guid)
        if result is None:
            return
        room_id = result.room.room_id
        self._to_lobby(CsOutRoomOut(room_id, guid))
        if result.removed:
            log.info("sala %d removida: sem jogadores", room_id)
            # Partida abandonada (ninguém ficou para jogar): o servidor cai e nada é gravado.
            self._match.finish(room_id)
            self._open.pop(room_id, None)
            self._left.pop(room_id, None)
            # Espectadores que sobraram saem junto: 322 para cada um, como em `room_expel`.
            for espectador in result.spectators:
                self._to_lobby(CsOutRoomOut(room_id, espectador))
            self._to_lobby(CsRemoveRoomOut(room_id))
            return
        if result.new_master is not None:
            log.info("sala %d: novo dono %d", room_id, result.new_master)
            self._to_lobby(CsChangeRoomMasterOut(room_id, result.new_master))
            if result.room.state == ROOM_WAITING:
                novo = result.room.members[result.new_master]
                self._to_room(result.room, CsReadyGameOut(result.new_master, False, novo.morats))
        self._after_leave(result.room)

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
            if not self._accepting():
                log.info("[%s] início recusado: desligamento em curso", session.peer)
                return [CsErrorEnvelope(CsOp.READY_GAME_ERROR, ERR_MATCH_START)]
            try:
                started = self._rooms.start(guid, req.morats)
            except RoomError as e:
                log.info("[%s] início recusado: %s", session.peer, e.reason.value)
                if e.reason is RoomReason.NOT_READY:
                    return [CsErrorEnvelope(CsOp.READY_GAME_ERROR, ERR_NOT_READY)]
                return []
            log.info("[%s] partida iniciada na sala %d", session.peer, started.room_id)
            # 412 PLAYING vai já ao canal; o 403 só sai quando o servidor aceita conexões.
            self._to_lobby(CsChangeRoomPropertyOut(started.room_id, state=started.state))
            return await self._launch(session.peer, started)
        try:
            room, ready = self._rooms.toggle_ready(guid, req.morats)
        except RoomError as e:
            log.info("[%s] pronto recusado: %s", session.peer, e.reason.value)
            return []
        self._to_room(room, CsReadyGameOut(guid, ready, req.morats))
        return []

    async def change_room_property(self, session: Session, payload: bytes) -> Sequence[Reply]:
        """411: o dono muda os campos marcados nas flags. A mudança vai ao canal inteiro (412)."""
        guid = self._lobby.guid_of(session)
        if guid is None:
            return []
        req = CsChangeRoomPropertyIn.unpack(payload)
        changes = _settings(req)
        try:
            room = self._rooms.configure(guid, changes)
        except RoomError as e:
            log.info("[%s] configuração recusada: %s", session.peer, e.reason.value)
            return []
        log.info("[%s] sala %d configurada: %s", session.peer, room.room_id, changes)
        self._to_lobby(
            CsChangeRoomPropertyOut(
                room.room_id,
                map_num=changes.get("map_num"),
                game_mode=changes.get("game_mode"),
                team_count=changes.get("team_count"),
                max_player=changes.get("max_player"),
                limit_time=changes.get("limit_time"),
                limit_score=changes.get("limit_score"),
            )
        )
        return []

    async def change_room_slot(self, session: Session, payload: bytes) -> Sequence[Reply]:
        guid = self._lobby.guid_of(session)
        if guid is None:
            return []
        req = CsChangeRoomSlotIn.unpack(payload)
        try:
            room = self._rooms.change_slot(guid, req.team)
        except RoomError as e:
            log.info("[%s] mudança de grupo recusada: %s", session.peer, e.reason.value)
            return []
        slot = room.members[guid].slot
        log.info("[%s] grupo %d: slot %d na sala %d", session.peer, req.team, slot, room.room_id)
        self._to_room(room, CsChangeRoomSlotOut(guid, slot))
        return []

    async def room_expel(self, session: Session, payload: bytes) -> Sequence[Reply]:
        """451: o dono tira do jogador da sala pelo nick. Não há resposta (452 não tem caso)."""
        guid = self._lobby.guid_of(session)
        if guid is None:
            return []
        req = CsRoomExpelIn.unpack(payload)
        room = self._rooms.room_of(guid)
        if room is None:
            return []
        target = next((g for g in room.members if self._lobby.nickname_of(g) == req.nickname), None)
        if target is None:
            log.info("[%s] expulsão: %r não está na sala", session.peer, req.nickname)
            return []
        playing = room.state == ROOM_PLAYING and target in room.in_game
        try:
            expelled = self._rooms.expel(guid, target)
        except RoomError as e:
            log.info("[%s] expulsão recusada: %s", session.peer, e.reason.value)
            return []
        if playing:
            self._left.setdefault(room.room_id, {}).setdefault(target, datetime.now(UTC))
        log.info("[%s] expulsou %d da sala %d", session.peer, expelled.guid, room.room_id)
        self._to_lobby(CsOutRoomOut(expelled.room.room_id, expelled.guid))
        self._after_leave(expelled.room)
        return []

    async def room_invite(self, session: Session, payload: bytes) -> Sequence[Reply]:
        """461: o dono convida um nick do canal. O convidado recebe 463; o dono, 462."""
        guid = self._lobby.guid_of(session)
        if guid is None:
            return []
        req = CsRoomInviteIn.unpack(payload)
        room = self._rooms.room_of(guid)
        if room is not None and room.master != guid:
            return [CsErrorEnvelope(CsOp.ROOM_INVITE_OUT, CERR_INVITE_ROOM_NOT_ADMIN)]
        target = self._lobby.guid_of_nick(req.nickname)
        if target is None:
            return [CsInviteResultOut(CERR_FIND_PLAYER)]
        try:
            room = self._rooms.invite(guid, target)
        except RoomError as e:
            log.info("[%s] convite recusado: %s", session.peer, e.reason.value)
            return [CsInviteResultOut(INVITE_CODES[e.reason])]
        inviter = self._lobby.nickname_of(guid) or ""
        self._lobby.send_to(
            [target], reply_body(CsRoomInviteOut(room.room_id, inviter), CHANNEL_NET_CODE)
        )
        log.info("[%s] convidou %r para a sala %d", session.peer, req.nickname, room.room_id)
        return [CsInviteResultOut(0)]

    async def room_invite_answer(self, session: Session, payload: bytes) -> Sequence[Reply]:
        """471: o convidado aceita ou recusa. Aceite entra na sala (como 311, sem senha) só com
        convite pendente para ela; sem convite, o pedido é recusado."""
        guid = self._lobby.guid_of(session)
        if guid is None:
            return []
        req = CsRoomInviteAnswerIn.unpack(payload)
        if not req.accept:
            self._rooms.decline_invite(guid)
            return []
        try:
            room = self._rooms.accept_invite(guid, req.room_id)
        except RoomError as e:
            log.info("[%s] aceite de convite recusado: %s", session.peer, e.reason.value)
            return []
        log.info("[%s] entrou na sala %d pelo convite", session.peer, room.room_id)
        return self._joined(room, guid)

    async def exit_play(self, session: Session, payload: bytes) -> Sequence[Reply]:
        """500: o jogador deixou a partida e fica na sala sem pronto (D210). Com o último a sair, a
        partida acaba e `_end` manda o estado a todos. Senão, só quem saiu recebe o 317 com o pronto
        zerado, porque o cliente trava Sair enquanto o pronto estiver ligado."""
        guid = self._lobby.guid_of(session)
        if guid is None:
            return []
        room = self._leave_game(guid)
        if room is None:
            return [CsExitPlayOut(0)]
        log.info("[%s] saiu da partida na sala %d (500)", session.peer, room.room_id)
        if room.match_over():
            record = self._end(room)
            if record is not None:
                await self._save(record, END_EXIT_PLAY)
            return [CsExitPlayOut(0)]
        return [CsExitPlayOut(0), self._records.room_players(room)]

    async def leave_hangar(self, session: Session, payload: bytes) -> Sequence[Reply]:
        """588 (OutHangar, sem corpo): só quem está em sala. Responde 589 com a própria chave e a
        posição de sala; sem a resposta, o cliente não volta da hangar para a página da sala."""
        guid = self._lobby.guid_of(session)
        if guid is None or self._rooms.room_of(guid) is None:
            return []
        return [CsLeaveHangarOut(guid)]

    def _leave_game(self, guid: int) -> Room | None:
        """Tira `guid` da partida em andamento, se estiver nela, e guarda a hora da saída para o
        tempo jogado (`with_played`). Devolve a sala, se houver."""
        room = self._rooms.room_of(guid)
        if room is None or room.state != ROOM_PLAYING or guid not in room.in_game:
            return room
        self._left.setdefault(room.room_id, {}).setdefault(guid, datetime.now(UTC))
        return self._rooms.exit_play(guid)

    async def enter_hangar(self, session: Session, payload: bytes) -> Sequence[Reply]:
        """586 (InHangar, sem corpo): só quem está em sala. Responde 587 com a própria chave; o
        cliente abre o hangar quando a chave é a dele (`NotifyEnterHanger`, XInterface 28991)."""
        guid = self._lobby.guid_of(session)
        if guid is None or self._rooms.room_of(guid) is None:
            return []
        return [CsEnterHangarOut(guid)]

    async def _launch(self, peer: str, room: Room) -> Sequence[Reply]:
        """Sobe o servidor da partida e manda o 403 quando ele aceita conexões.
        Falha devolve a sala à espera e avisa o dono com o erro 241000201."""
        try:
            plan = await self._plan(room)
            endpoint = await self._match.start(
                room.room_id, plan, partial(self._match_exited, room.room_id)
            )
        except MatchStartError as e:
            log.warning("[%s] partida da sala %d não começou: %s", peer, room.room_id, e)
            self._end(room)
            return [CsErrorEnvelope(CsOp.READY_GAME_ERROR, ERR_MATCH_START)]
        if self._rooms.get(room.room_id) is not room:
            # A sala acabou enquanto o servidor subia (todos saíram).
            self._match.finish(room.room_id)
            return []
        self._open[room.room_id] = self._open_record(room, plan)
        # O 402 do dono pronto dispara a contagem nos clientes e libera a entrada (D77).
        dono = room.members[room.master]
        self._to_room(room, CsReadyGameOut(room.master, True, dono.morats))
        self._to_room(room, CsStartGameOut(endpoint.host, endpoint.port))
        return []

    async def _match_exited(self, room_id: int) -> None:
        """O servidor da partida caiu sozinho depois de pronto: a partida acaba e a sala espera."""
        room = self._rooms.get(room_id)
        if room is None:
            return
        record = self._end(room)
        if record is not None:
            await self._save(record, END_SERVER_EXIT)

    def _end(self, room: Room) -> MatchRecord | None:
        """Fecha a partida na memória: servidor encerrado, sala de volta à espera e avisos.
        Devolve o histórico a gravar. Sala que já não existe ou não está jogando não faz nada."""
        if self._rooms.get(room.room_id) is not room or room.state != ROOM_PLAYING:
            return None
        # Parada pelo console em segundo plano: o motor grava o log antes do `_save` que o lê.
        self._logs[room.room_id] = asyncio.get_running_loop().create_task(
            self._match.end(room.room_id)
        )
        self._rooms.finish(room.room_id)
        self._to_lobby(CsChangeRoomPropertyOut(room.room_id, state=ROOM_WAITING))
        for guid, member in room.members.items():
            self._to_room(room, CsReadyGameOut(guid, member.ready, member.morats))
        self._to_room(room, self._records.room_players(room))
        record = self._open.pop(room.room_id, None)
        if record is None:
            return None
        return with_played(record, self._left.pop(room.room_id, {}), datetime.now(UTC))

    async def end_matches(self) -> None:
        """Desligamento no prazo: encerra as partidas em andamento e grava cada uma com
        `server_shutdown`. Espera as gravações pendentes; as salas voltam à espera antes disso."""
        records: list[MatchRecord] = []
        for room in self._rooms.all():
            if room.state != ROOM_PLAYING:
                continue
            record = self._end(room)
            if record is not None:
                records.append(record)
        resultados = await asyncio.gather(
            *(self._save(record, END_SHUTDOWN) for record in records),
            *self._saves,
            return_exceptions=True,
        )
        for erro in resultados:
            if isinstance(erro, BaseException):
                log.error("gravação no desligamento falhou", exc_info=erro)

    def _after_leave(self, room: Room) -> None:
        """Quem saiu (ou foi expulso) pode ter sido o último em jogo: então a partida acaba."""
        if not room.match_over():
            return
        record = self._end(room)
        if record is not None:
            task = asyncio.get_running_loop().create_task(self._save(record, END_EXIT_PLAY))
            self._saves.add(task)
            task.add_done_callback(self._saves.discard)

    async def _save(self, record: MatchRecord, reason: str) -> None:
        """Grava o histórico com o bloco `GameEnded` do log (quando houver), e exp e LD na mesma
        transação. Depois avisa o saldo a quem ganhou. Erro de banco é logado: a sala já voltou à
        espera."""
        parada = self._logs.pop(record.room_id, None)
        jogadores: tuple[GameEndedPlayer, ...] = ()
        if parada is not None:
            try:
                jogadores = await parada
            except Exception:
                log.exception("log da partida da sala %d não lido", record.room_id)
        ended = with_game_end(
            replace(record, ended_at=datetime.now(UTC), end_reason=reason), jogadores
        )
        if self._matches is None:
            return
        try:
            await self._matches.save(ended)
        except Exception:
            log.exception("histórico da sala %d não gravado", record.room_id)
            return
        try:
            await self._avisa_recompensas(ended)
        except Exception:
            log.exception("saldo da partida da sala %d não avisado", record.room_id)

    async def _avisa_recompensas(self, match: MatchRecord) -> None:
        """Saldo novo de quem ganhou exp ou LD: linha de economia e pushes 900 (cash) e 902 (LD)."""
        if self._progression is None:
            return
        for p in match.players:
            if p.exp is None and p.money is None:
                continue
            saldo = await self._progression.get(p.account_id)
            if self._audit is not None:
                self._audit.record_account(
                    p.account_id,
                    p.nickname,
                    "match_reward",
                    match_uuid=match.uuid,
                    room_id=match.room_id,
                    exp=p.exp,
                    ld=p.money,
                    total_exp_after=saldo.total_exp,
                    ld_after=saldo.ld,
                )
            para = [p.account_id]
            self._lobby.send_to(
                para, reply_body(CsChargeCashOut(cash=saldo.cash), CHANNEL_NET_CODE)
            )
            self._lobby.send_to(
                para, reply_body(CsChargePointOut(point=saldo.ld), CHANNEL_NET_CODE)
            )

    async def _plan(self, room: Room) -> MatchPlan:
        try:
            record = self._maps.get(room.map_num)
        except ValueError as e:
            raise MatchStartError(f"catálogo de mapas indisponível: {e}") from e
        if record is None:
            raise MatchStartError(f"mapa {room.map_num} não existe no catálogo")
        plan = build_plan(room, record)
        return replace(plan, loadout=await self._loadout_of(room, plan.game_class))

    async def _loadout_of(self, room: Room, game_class: str) -> tuple[str, ...]:
        """Equipamento de cada jogador (LMEmu.ini, D190). Erro do catálogo não impede a partida: ela
        sobe sem linhas e o motor usa o padrão do cliente para todos."""
        if self._loadout is None:
            return ()
        membros = [
            LoadoutMember(
                guid,
                self._lobby.nickname_of(guid) or "",
                membro.slot,
                membro.morats,
                spectator=membro.spectator,
            )
            for guid, membro in room.members.items()
        ]
        try:
            return await self._loadout.lines(membros, game_class, room.team_count)
        except ValueError as e:
            log.warning("sala %d sem equipamento no LMEmu.ini: %s", room.room_id, e)
            return ()

    def _open_record(self, room: Room, plan: MatchPlan) -> MatchRecord:
        """Histórico no início: quem joga agora está na sala com slot de jogador. Espectador não
        entra no histórico nem nas recompensas (D197). Resultado e fim vêm em `_save`."""
        now = datetime.now(UTC)
        players = tuple(
            PlayerMatchStats(
                account_id=guid,
                nickname=self._lobby.nickname_of(guid) or "",
                slot=member.slot,
                team=None,
                is_master=guid == room.master,
            )
            for guid, member in room.players().items()
        )
        return MatchRecord(
            room_id=room.room_id,
            map_record_id=room.map_num,
            map_file=plan.map_file,
            game_mode=room.game_mode,
            game_class=plan.game_class,
            team_count=room.team_count,
            max_players=plan.max_players,
            time_limit=plan.time_limit,
            goal_score=plan.goal_score,
            started_at=now,
            ended_at=now,
            end_reason="",
            players=players,
            uuid=str(uuid4()),
        )

    def _to_lobby(self, reply: Reply) -> None:
        self._lobby.broadcast(reply_body(reply, CHANNEL_NET_CODE))

    def _to_room(self, room: Room, reply: Reply) -> None:
        self._lobby.send_to(room.members, reply_body(reply, CHANNEL_NET_CODE))
