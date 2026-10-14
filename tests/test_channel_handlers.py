"""Montagem do Channel Server (`ChannelHandlers`), registros do canal e handlers de salas em
memória."""

import struct

from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.match import MapRecord
from landmass_emu.domain.rooms import Room, Rooms
from landmass_emu.domain.session_keys import MemorySessionKeyRegistry
from landmass_emu.handlers.channel import ChannelHandlers
from landmass_emu.handlers.channel.lists import ListHandlers
from landmass_emu.handlers.channel.records import ChannelRecords
from landmass_emu.handlers.channel.rooms import (
    CERR_FIND_PLAYER,
    CERR_IN_ROOM,
    CERR_INVITE_ROOM_NOT_ADMIN,
    RoomHandlers,
)
from landmass_emu.hosting.fixed import FixedMatchHost
from landmass_emu.net.session import Session
from landmass_emu.ports.match_host import GameEndpoint
from landmass_emu.protocol.channel import (
    CsChangeRoomPropertyIn,
    CsErrorEnvelope,
    CsInviteResultOut,
    CsOp,
    CsRefreshPlayerListOut,
    CsRoomEntryOut,
    CsRoomExpelIn,
    CsRoomInfoOut,
    CsRoomPlayer,
    CsRoomPlayerInfoOut,
)
from landmass_emu.protocol.header import unpack_header
from landmass_emu.protocol.message import cfield, cstr
from landmass_emu.protocol.progression import CsProgressionOp
from landmass_emu.protocol.shop import CsShopOp


class _Mapas:
    """Catálogo de teste: todo mapa existe, com 32 vagas."""

    def get(self, record_id: int) -> MapRecord | None:
        return MapRecord(record_id=record_id, file_name="ONS-Treino", player_max=32, op_type=0)


class _Recebedor:
    """Destino de corpos: guarda o que recebe. Satisfaz `domain.lobby.Recipient`."""

    def __init__(self) -> None:
        self.corpos: list[bytes] = []

    def send(self, body: bytes) -> None:
        self.corpos.append(body)


def _montagem() -> tuple[RoomHandlers, Lobby, Rooms]:
    lobby = Lobby()
    rooms = Rooms()
    handlers = RoomHandlers(
        lobby,
        rooms,
        ChannelRecords(lobby),
        FixedMatchHost(GameEndpoint("127.0.0.1", 7777)),
        _Mapas(),
        None,
    )
    return handlers, lobby, rooms


def _entra_no_lobby(lobby: Lobby, guid: int, nick: str, total_exp: int = 0) -> Session:
    sessao = Session(peer=nick)
    lobby.join(guid, sessao, nick, total_exp)
    return sessao


def _criar_sala(rooms: Rooms, dono: int) -> Room:
    return rooms.create(
        dono,
        name="Sala Azul",
        password="",
        scale=0,
        game_mode=1,
        map_num=1,
        max_player=4,
        team_count=1,
        limit_time=10,
        limit_score=10,
    )


def _corpos(sessao: Session) -> list[tuple[int, bytes]]:
    """Corpos na fila de `sessao` como (opcode, payload), em ordem; esvazia a fila."""
    saida: list[tuple[int, bytes]] = []
    while not sessao.outbox.empty():
        cabecalho, payload = unpack_header(sessao.outbox.get_nowait())
        saida.append((cabecalho.opcode, payload))
    return saida


def test_tabela_do_roteador_cobre_entrada_chat_salas_e_listas() -> None:
    # As opções não são usadas na montagem; o teste só confere as chaves do roteador.
    handlers = ChannelHandlers(
        MemorySessionKeyRegistry(),
        Lobby(),
        Rooms(),
        None,
        None,
        FixedMatchHost(GameEndpoint("127.0.0.1", 7777)),
        _Mapas(),
        None,
        None,
        None,
        None,
    )
    esperados = {
        CsOp.HEARTBEAT,
        CsOp.IN_CHANNEL_SERVER,
        CsOp.IN_CHANNEL,
        CsOp.OUT_CHANNEL,
        CsOp.SEND_MESSAGE,
        CsOp.SAVE_OPTION,
        CsOp.CREATE_ROOM,
        CsOp.IN_ROOM,
        CsOp.OUT_ROOM,
        CsOp.READY_GAME,
        CsOp.CHANGE_ROOM_PROPERTY,
        CsOp.CHANGE_ROOM_SLOT,
        CsOp.ROOM_EXPEL,
        CsOp.ROOM_INVITE,
        CsOp.ROOM_INVITE_ANSWER,
        CsOp.REFRESH_PLAYER_LIST,
        CsOp.REFRESH_ROOM_LIST,
        CsProgressionOp.TUTORIAL_CLEAR,
        CsShopOp.ITEM_BUY_IN,
    }
    assert esperados <= set(handlers.router)
    # 700 é o `/EXPEL` do console: não é executado (ver `CsExpelPlayerIn`).
    assert CsOp.EXPEL_PLAYER not in handlers.router


def test_registros_do_lobby_na_ordem_de_entrada_com_nick() -> None:
    lobby = Lobby()
    lobby.join(7, _Recebedor(), "Ana")
    lobby.join(9, _Recebedor(), "Bia")
    jogadores = ChannelRecords(lobby).lobby_players()
    assert [(j.client_guid, j.nick) for j in jogadores] == [(7, "Ana"), (9, "Bia")]


def test_jogadores_da_sala_levam_o_nick_do_lobby_e_o_registro_de_sala() -> None:
    lobby = Lobby()
    lobby.join(7, _Recebedor(), "Ana")
    lobby.join(9, _Recebedor(), "Bia")
    rooms = Rooms()
    sala = _criar_sala(rooms, 7)
    rooms.join(sala.room_id, 9, "")
    records = ChannelRecords(lobby)
    jogadores = records.room_players(sala).players
    assert [(j.client_guid, j.nick, j.slot) for j in jogadores] == [(7, "Ana", 0), (9, "Bia", 1)]
    registro = records.room(sala)
    assert registro.curr_player == 2
    assert registro.has_password is False


async def test_total_exp_do_lobby_vai_a_151_317_e_548() -> None:
    lobby = Lobby()
    rooms = Rooms()
    records = ChannelRecords(lobby)
    ana = _entra_no_lobby(lobby, 7, "Ana", total_exp=1234)
    _entra_no_lobby(lobby, 9, "Bia", total_exp=5)
    sala = _criar_sala(rooms, 7)
    # 151: entrada do lobby com a exp de quem está no canal.
    assert records.lobby_players()[0].total_exp == 1234
    # 317: a lista da sala traz a mesma exp.
    assert records.room_players(sala).players[0].total_exp == 1234
    # 548: resposta ao pedido 546 (`i32 channel`, `u8 count` @4, guids a partir de @8).
    pedido = bytes(4) + bytes((1,)) + bytes(3) + struct.pack("<i", 7)
    [resposta] = await ListHandlers(lobby, rooms, records).refresh_player_list(ana, pedido)
    assert isinstance(resposta, CsRefreshPlayerListOut)
    assert resposta.players[0].total_exp == 1234


async def test_entrada_na_sala_manda_549_a_quem_ja_esta_e_312_ao_resto_do_canal() -> None:
    handlers, lobby, rooms = _montagem()
    ana = _entra_no_lobby(lobby, 7, "Ana")
    bia = _entra_no_lobby(lobby, 9, "Bia")
    cris = _entra_no_lobby(lobby, 11, "Cris")
    sala = _criar_sala(rooms, 7)

    respostas = await handlers.in_room(bia, struct.pack("<i16s", sala.room_id, b""))

    # Quem entra recebe 314 e 317 como resposta; o resto vem pelo canal.
    assert [type(r) for r in respostas] == [CsRoomInfoOut, CsRoomPlayerInfoOut]
    # Ana já estava na sala: só o 549 (nó e slot de quem chegou), sem o 312 que também soma.
    [(opcode, entrada)] = _corpos(ana)
    assert opcode == CsOp.ROOM_ENTRY_OUT
    esperado = CsRoomPlayer(client_guid=9, slot=1, ready=False, morats=0, nick="Bia")
    assert entrada == CsRoomEntryOut(esperado).pack()
    assert entrada[0x28] == 1
    # Bia e Cris (fora da sala) recebem o 312, que põe a sala na lista e soma para cada um.
    for sessao in (bia, cris):
        [(opcode, payload)] = _corpos(sessao)
        assert opcode == CsOp.IN_ROOM_OUT
        assert struct.unpack("<iii", payload) == (sala.room_id, 9, 1)


async def test_convite_461_chega_a_463_no_convidado_e_responde_462_ao_dono() -> None:
    handlers, lobby, rooms = _montagem()
    ana = _entra_no_lobby(lobby, 7, "Ana")
    cris = _entra_no_lobby(lobby, 11, "Cris")
    sala = _criar_sala(rooms, 7)

    resposta = await handlers.room_invite(ana, cfield("Cris", 17))

    assert resposta == [CsInviteResultOut(0)]
    assert _corpos(ana) == []
    [(opcode, payload)] = _corpos(cris)
    assert opcode == CsOp.ROOM_INVITE_NOTIFY
    assert struct.unpack_from("<i", payload, 0) == (sala.room_id,)
    assert cstr(payload[4:21]) == "Ana"


async def test_convite_recusado_com_cerr_e_so_o_dono_convida() -> None:
    handlers, lobby, rooms = _montagem()
    ana = _entra_no_lobby(lobby, 7, "Ana")
    bia = _entra_no_lobby(lobby, 9, "Bia")
    _entra_no_lobby(lobby, 11, "Cris")
    sala = _criar_sala(rooms, 7)
    rooms.join(sala.room_id, 9, "")

    # Nick fora do canal: 462 com CERR_FIND_PLAYER.
    assert await handlers.room_invite(ana, cfield("Zeca", 17)) == [
        CsInviteResultOut(CERR_FIND_PLAYER)
    ]
    # Quem não é dono: envelope de -4061 com o opcode real 462 (o cliente não mostra nada).
    assert await handlers.room_invite(bia, cfield("Cris", 17)) == [
        CsErrorEnvelope(CsOp.ROOM_INVITE_OUT, CERR_INVITE_ROOM_NOT_ADMIN)
    ]
    # Convidado já na sala: CERR_IN_ROOM.
    assert await handlers.room_invite(ana, cfield("Bia", 17)) == [CsInviteResultOut(CERR_IN_ROOM)]
    assert _corpos(bia) == []


async def test_convite_aceito_entra_na_sala_e_recusa_ou_sem_convite_nao_entra() -> None:
    handlers, lobby, rooms = _montagem()
    ana = _entra_no_lobby(lobby, 7, "Ana")
    cris = _entra_no_lobby(lobby, 11, "Cris")
    dani = _entra_no_lobby(lobby, 13, "Dani")
    sala = _criar_sala(rooms, 7)
    await handlers.room_invite(ana, cfield("Cris", 17))
    await handlers.room_invite(ana, cfield("Dani", 17))
    _corpos(ana)  # o convite (463) foi para Cris e Dani; a fila de Ana está vazia

    # Dani recusa: não entra.
    recusa = struct.pack("<iB3x", sala.room_id, 0)
    assert await handlers.room_invite_answer(dani, recusa) == []
    assert rooms.room_of(13) is None

    # Cris aceita: entra sem senha e recebe 314 e 317 como resposta.
    aceite = struct.pack("<iB3x", sala.room_id, 1)
    respostas = await handlers.room_invite_answer(cris, aceite)
    assert [type(r) for r in respostas] == [CsRoomInfoOut, CsRoomPlayerInfoOut]
    assert rooms.room_of(11) is sala
    # Ana, que está na sala, recebe só o 549 de Cris.
    assert [op for op, _ in _corpos(ana)] == [CsOp.ROOM_ENTRY_OUT]

    # Dani recusou antes: sem convite pendente, o aceite não o põe na sala.
    assert await handlers.room_invite_answer(dani, aceite) == []
    assert rooms.room_of(13) is None


async def test_451_expulsa_pelo_nick_so_o_dono_e_avisa_o_canal_com_322() -> None:
    handlers, lobby, rooms = _montagem()
    ana = _entra_no_lobby(lobby, 7, "Ana")
    bia = _entra_no_lobby(lobby, 9, "Bia")
    cris = _entra_no_lobby(lobby, 11, "Cris")
    sala = _criar_sala(rooms, 7)
    rooms.join(sala.room_id, 9, "")

    assert await handlers.room_expel(bia, CsRoomExpelIn("Ana").pack()) == []
    assert rooms.room_of(7) is sala
    assert _corpos(bia) == []

    assert await handlers.room_expel(ana, CsRoomExpelIn("Bia").pack()) == []
    assert rooms.room_of(9) is None
    for sessao in (ana, bia, cris):
        assert [op for op, _ in _corpos(sessao)] == [CsOp.OUT_ROOM_OUT]


async def test_411_do_dono_muda_a_sala_e_manda_412_ao_canal() -> None:
    handlers, lobby, rooms = _montagem()
    ana = _entra_no_lobby(lobby, 7, "Ana")
    bia = _entra_no_lobby(lobby, 9, "Bia")
    sala = _criar_sala(rooms, 7)
    rooms.join(sala.room_id, 9, "")
    # MAP | LIMIT_PLAYER: só map_num e max_player mudam; o resto vem mas é ignorado.
    pedido = struct.pack("<BxHBBBBH", 0x05, 9, 2, 3, 4, 10, 50)
    assert CsChangeRoomPropertyIn.unpack(pedido).flags == 0x05

    assert await handlers.change_room_property(bia, pedido) == []
    assert sala.map_num == 1
    assert _corpos(bia) == []

    assert await handlers.change_room_property(ana, pedido) == []
    assert sala.map_num == 9 and sala.max_player == 4
    assert sala.game_mode == 1
    for sessao in (ana, bia):
        [(opcode, corpo)] = _corpos(sessao)
        assert opcode == CsOp.CHANGE_ROOM_PROPERTY_OUT
        assert struct.unpack_from("<i", corpo, 0) == (sala.room_id,)
        assert corpo[4] == 0x05
        assert struct.unpack_from("<h", corpo, 6) == (9,)
        assert corpo[0xA] == 4
