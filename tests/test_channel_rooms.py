"""Salas: codec com offsets conferidos nos bytes (re/rooms.md) e regras do domínio em memória."""

import struct

import pytest

from landmass_emu.domain.rooms import ROOM_PLAYING, RoomError, RoomReason, Rooms
from landmass_emu.protocol.channel import (
    ROOM_HEAD_SIZE,
    ROOM_INFO_SIZE,
    ROOM_RECORD_SIZE,
    ROOM_SLOTS,
    CsChangeRoomMasterOut,
    CsChangeRoomSlotIn,
    CsChangeRoomSlotOut,
    CsChannelRoomInfoOut,
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
    CsRefreshRoomListIn,
    CsRefreshRoomListOut,
    CsRemoveRoomOut,
    CsRoom,
    CsRoomInfoOut,
    CsRoomPlayer,
    CsRoomPlayerInfoOut,
    CsRoomStateOut,
    CsStartGameOut,
)


def _sala(**kw: object) -> CsRoom:
    base: dict[str, object] = {
        "room_id": 7,
        "name": "Sala",
        "has_password": False,
        "state": 1,
        "game_mode": 2,
        "team_count": 3,
        "curr_player": 1,
        "max_player": 4,
        "map_num": 9,
        "limit_score": 50,
        "limit_time": 10,
        "master": 0x0102,
        "slots": (0x0102,) + (-1,) * (ROOM_SLOTS - 1),
    }
    base.update(kw)
    return CsRoom(**base)  # type: ignore[arg-type]


def test_criar_sala_entrada_de_301_offsets() -> None:
    payload = struct.pack("<32s16s6iH", b"Sala Azul", b"abc", 1, 2, 3, 4, 5, 6, 7)
    assert len(payload) == 74
    req = CsCreateRoomIn.unpack(payload)
    assert req == CsCreateRoomIn("Sala Azul", "abc", 1, 2, 3, 4, 5, 6, 7)
    # max_player é o quarto dword (@60), limit_score o u16 final (@72).
    assert struct.unpack_from("<i", payload, 60) == (4,)
    assert struct.unpack_from("<H", payload, 72) == (7,)


def test_criar_sala_rejeita_payload_curto() -> None:
    with pytest.raises(ValueError):
        CsCreateRoomIn.unpack(bytes(73))


def test_entrar_sala_entrada_de_311_offsets() -> None:
    payload = struct.pack("<i16s", 5, b"segredo")
    assert len(payload) == 20
    assert CsInRoomIn.unpack(payload) == CsInRoomIn(5, "segredo")
    with pytest.raises(ValueError):
        CsInRoomIn.unpack(bytes(19))


def test_registro_de_sala_tem_612_bytes_e_offsets_do_no() -> None:
    raw = _sala(has_password=True, name="Sala Azul").pack()
    assert len(raw) == ROOM_RECORD_SIZE == 612
    assert struct.unpack_from("<i", raw, 0x00) == (7,)  # chave de busca de 302, 312, 322...
    assert raw[0x10 : 0x10 + 9] == b"Sala Azul"
    assert raw[0x10 + 9] == 0  # NUL do char[32]
    assert raw[0x30] == 1  # senha
    assert raw[0x38] == 1  # estado: espera (402 compara value+0x38 com 1)
    assert raw[0x39] == 2  # modo de jogo
    assert raw[0x3A] == 3  # times
    assert raw[0x3B] == 1  # jogadores (conta o dono)
    assert raw[0x3D] == 4  # máximo
    assert raw[0x3E] == 1  # aberta
    assert struct.unpack_from("<h", raw, 0x40) == (9,)  # mapa
    assert struct.unpack_from("<h", raw, 0x44) == (50,)  # limite de pontos
    assert raw[0x46] == 10  # limite de tempo
    assert struct.unpack_from("<i", raw, 0x4C) == (0x0102,)  # dono


def test_registro_de_sala_slots_e_espectadores_vazios_sao_menos_um() -> None:
    raw = _sala(slots=(0x0102, 0x0203) + (-1,) * (ROOM_SLOTS - 2)).pack()
    assert struct.unpack_from("<i", raw, 0x50) == (0x0102,)
    assert struct.unpack_from("<i", raw, 0x54) == (0x0203,)
    assert struct.unpack_from("<i", raw, 0x50 + 4 * 2) == (-1,)
    # 70 slots terminam em 0x168 (node+0x178); espectadores em 0x174 com 60 entradas até 0x264.
    assert struct.unpack_from("<i", raw, 0x50 + 4 * (ROOM_SLOTS - 1)) == (-1,)
    assert raw[0x168:0x174] == bytes(12)
    for j in range(60):
        assert struct.unpack_from("<i", raw, 0x174 + 4 * j) == (-1,)
    assert ROOM_RECORD_SIZE == 0x174 + 4 * 60


def test_registro_de_sala_rejeita_slots_com_tamanho_errado() -> None:
    with pytest.raises(ValueError):
        _sala(slots=(1, 2)).pack()


def test_entrada_de_141_e_o_inicio_do_registro() -> None:
    sala = _sala(name="Lista")
    head = sala.head()
    assert len(head) == ROOM_HEAD_SIZE == 0x44
    assert head == sala.pack()[:0x44]
    lista = CsChannelRoomInfoOut((sala, _sala(room_id=8, name="Outra"))).pack()
    assert lista[0:2] == b"\x02\x00"
    assert len(lista) == 2 + 2 * 0x44
    assert lista[2 : 2 + 0x44] == head
    assert struct.unpack_from("<i", lista, 2 + 0x44) == (8,)
    assert CsChannelRoomInfoOut().pack() == b"\x00\x00"


def test_criacao_302_e_o_registro_inteiro() -> None:
    raw = CsCreateRoomOut(_sala()).pack()
    assert CsCreateRoomOut.opcode == CsOp.CREATE_ROOM_OUT == 302
    assert len(raw) == 612


def test_sala_info_314_offsets_do_corpo() -> None:
    raw = CsRoomInfoOut(_sala(limit_time=10, limit_score=50)).pack()
    assert len(raw) == ROOM_INFO_SIZE == 0x38
    assert struct.unpack_from("<h", raw, 0x00) == (50,)  # limite de pontos (node+0x54)
    assert raw[0x02] == 10  # limite de tempo (node+0x56)
    assert struct.unpack_from("<i", raw, 0x08) == (0x0102,)  # dono (node+0x5c)
    assert struct.unpack_from("<i", raw, 0x0C) == (7,)  # chave de busca (body+0xc)
    assert raw[0x10] == 1 and raw[0x11] == 2 and raw[0x12] == 3 and raw[0x13] == 4
    assert raw[0x14] == 1
    assert struct.unpack_from("<h", raw, 0x16) == (9,)  # mapa (node+0x50)
    assert CsRoomInfoOut.opcode == CsOp.ROOM_INFO_OUT == 314


def test_entrada_de_jogador_317_tem_48_bytes_e_offsets() -> None:
    entradas = (
        CsRoomPlayer(client_guid=0x11, slot=0, ready=True, morats=3),
        CsRoomPlayer(client_guid=0x22, slot=1, ready=False, morats=0),
    )
    raw = CsRoomPlayerInfoOut(entradas).pack()
    assert raw[0] == 2
    assert len(raw) == 1 + 2 * 0x30
    primeiro = raw[1 : 1 + 0x30]
    assert struct.unpack_from("<i", primeiro, 0x00) == (0x11,)  # guid (+0xa0)
    assert struct.unpack_from("<i", primeiro, 0x04) == (0,)  # total_exp (+0x3c), zero
    assert primeiro[0x28] == 0  # slot
    assert primeiro[0x29] == 1  # pronto (bit0 de +0xac)
    assert primeiro[0x2A] == 0  # flag de estado: 0 vira 0x23 (em sala)
    assert primeiro[0x2B] == 0  # pc_room
    assert struct.unpack_from("<i", primeiro, 0x2C) == (3,)  # select_morats_id (+0xb4)
    segundo = raw[1 + 0x30 : 1 + 0x60]
    assert struct.unpack_from("<i", segundo, 0x00) == (0x22,)
    assert segundo[0x28] == 1 and segundo[0x29] == 0
    assert CsRoomPlayerInfoOut(()).pack() == b"\x00"


def test_jogador_de_sala_tem_o_nick_do_registro_de_151() -> None:
    entrada = CsRoomPlayer(client_guid=5, slot=0, ready=False, morats=0, nick="Ana").pack()
    assert len(entrada) == 48
    assert entrada[0x08:0x18] == b"Ana" + bytes(13)
    assert entrada[0x18:0x28] == bytes(16)  # campos sem valor no lobby


def test_pedido_545_limita_a_9_salas_e_resposta_547_offsets() -> None:
    corpo = bytearray(44)
    corpo[4] = 12
    for i in range(9):
        struct.pack_into("<i", corpo, 8 + 4 * i, 100 + i)
    assert CsRefreshRoomListIn.unpack(bytes(corpo)).room_guids == tuple(range(100, 109))
    with pytest.raises(ValueError):
        CsRefreshRoomListIn.unpack(bytes(7))

    sala = _sala(state=2, game_mode=5, team_count=6, curr_player=3, max_player=8, map_num=12)
    raw = CsRefreshRoomListOut((sala,)).pack()
    assert len(raw) == 4 + 16
    assert raw[0] == 1 and raw[1:4] == bytes(3)
    assert struct.unpack_from("<i", raw, 4) == (7,)  # room_guid
    assert raw[8:15] == bytes((2, 5, 6, 3, 0, 8, 1))  # state, mode, team, curr, spect, max, open
    assert struct.unpack_from("<H", raw, 16) == (12,)  # map_num
    assert CsRefreshRoomListOut(()).pack() == bytes(4)
    assert CsRefreshRoomListOut.opcode == CsOp.REFRESH_ROOM_LIST_OUT == 547


def test_saida_322_e_master_332_e_remocao_342() -> None:
    assert struct.unpack("<ii", CsOutRoomOut(7, 0x33).pack()) == (7, 0x33)
    assert struct.unpack("<ii", CsChangeRoomMasterOut(7, 0x44).pack()) == (7, 0x44)
    assert CsRemoveRoomOut(7).pack() == struct.pack("<i", 7)
    assert CsOutRoomOut.opcode == CsOp.OUT_ROOM_OUT == 322
    assert CsChangeRoomMasterOut.opcode == CsOp.CHANGE_ROOM_MASTER_OUT == 332
    assert CsRemoveRoomOut.opcode == CsOp.REMOVE_ROOM_OUT == 342


def test_entrada_312_sucesso_offsets() -> None:
    assert struct.unpack("<iii", CsInRoomOut(7, 0x33, 2).pack()) == (7, 0x33, 2)
    assert CsInRoomOut.opcode == CsOp.IN_ROOM_OUT == 312


def test_erro_312_usa_negativo_com_codigo_no_short_e_foto_da_sala() -> None:
    sala = _sala(
        state=2,
        game_mode=5,
        team_count=6,
        curr_player=3,
        curr_spectator=1,
        max_player=8,
        map_num=12,
    )
    raw = CsInRoomError(1701, 7, sala).pack()
    assert len(raw) == 0x12
    assert struct.unpack_from("<i", raw, 0) == (1701 - 0x10000,)
    assert struct.unpack_from("<h", raw, 0) == (1701,)  # `(short)` que o cliente lê
    assert struct.unpack_from("<i", raw, 4) == (7,)  # chave de busca
    # estado, modo, times, jogadores, espectadores, máximo, aberta
    assert raw[8:15] == bytes((2, 5, 6, 3, 1, 8, 1))
    assert struct.unpack_from("<h", raw, 0x10) == (12,)


def test_erro_312_sem_sala_zera_a_foto() -> None:
    raw = CsInRoomError(1001, 99).pack()
    assert struct.unpack_from("<h", raw, 0) == (1001,)
    assert raw[8:0x12] == bytes(0x0A)


def test_pronto_402_e_inicio_403_offsets() -> None:
    pronto = CsReadyGameOut(0x11, True, 4).pack()
    assert len(pronto) == 12
    assert struct.unpack_from("<i", pronto, 0) == (0x11,)
    assert pronto[4] == 1 and pronto[5:8] == bytes(3)
    assert struct.unpack_from("<i", pronto, 8) == (4,)
    inicio = CsStartGameOut("127.0.0.1", 7777).pack()
    assert len(inicio) == 18
    assert inicio[:16] == b"127.0.0.1" + bytes(7)
    assert struct.unpack_from("<H", inicio, 16) == (7777,)
    assert CsReadyGameOut.opcode == CsOp.READY_GAME_OUT == 402
    assert CsStartGameOut.opcode == CsOp.START_GAME_OUT == 403


def test_estado_412_com_mascara_de_state_no_byte_0xf() -> None:
    raw = CsRoomStateOut(7, 2).pack()
    assert len(raw) == 16
    assert struct.unpack_from("<i", raw, 0) == (7,)
    assert raw[4] == 0x20
    assert raw[0xF] == 2
    assert CsRoomStateOut.opcode == CsOp.CHANGE_ROOM_PROPERTY_OUT == 412


def test_slot_420_421_e_expulsao_700_701() -> None:
    assert CsChangeRoomSlotIn.unpack(b"\x03") == CsChangeRoomSlotIn(3)
    with pytest.raises(ValueError):
        CsChangeRoomSlotIn.unpack(b"")
    assert CsChangeRoomSlotOut(0x11, 3).pack() == struct.pack("<iB3x", 0x11, 3)
    assert CsExpelPlayerIn.unpack(struct.pack("<i", 2) + bytes(14)) == CsExpelPlayerIn(2)
    with pytest.raises(ValueError):
        CsExpelPlayerIn.unpack(b"\x01")
    assert CsExpelPlayerOut().pack() == bytes(4)
    assert CsChangeRoomSlotOut.opcode == CsOp.CHANGE_ROOM_SLOT_OUT == 421
    assert CsExpelPlayerOut.opcode == CsOp.EXPEL_PLAYER_OUT == 701


def test_pronto_401_le_um_byte() -> None:
    assert CsReadyGameIn.unpack(b"\x05") == CsReadyGameIn(5)
    with pytest.raises(ValueError):
        CsReadyGameIn.unpack(b"")


def test_envelope_de_erro_com_opcode_real_e_codigo() -> None:
    raw = CsErrorEnvelope(CsOp.READY_GAME_ERROR, 241002702).pack()
    assert len(raw) == 8
    assert struct.unpack_from("<H", raw, 0) == (404,)
    assert struct.unpack_from("<i", raw, 4) == (241002702,)
    assert CsErrorEnvelope.opcode == CsOp.ERROR == 54


# ---- Domínio -----------------------------------------------------------------------------------


def _criar(rooms: Rooms, dono: int, *, nome: str = "Sala", senha: str = "", max_player: int = 4):
    return rooms.create(
        dono,
        name=nome,
        password=senha,
        scale=0,
        game_mode=1,
        map_num=1,
        max_player=max_player,
        team_count=1,
        limit_time=10,
        limit_score=10,
    )


def test_dominio_criar_entrar_e_slots() -> None:
    rooms = Rooms()
    sala = _criar(rooms, 1)
    assert sala.room_id == 1 and sala.master == 1
    assert sala.members[1].slot == 0 and sala.members[1].ready
    rooms.join(1, 2, "")
    assert rooms.room_of(2) is sala and sala.members[2].slot == 1
    rooms.change_slot(2, 3)
    assert sala.members[2].slot == 3
    with pytest.raises(RoomError) as exc:
        rooms.change_slot(1, 3)
    assert exc.value.reason is RoomReason.SLOT_TAKEN


def test_dominio_senha_cheia_e_sala_inexistente() -> None:
    rooms = Rooms()
    _criar(rooms, 1, senha="segredo", max_player=2)
    with pytest.raises(RoomError) as wrong:
        rooms.join(1, 2, "errada")
    assert wrong.value.reason is RoomReason.WRONG_PASSWORD
    rooms.join(1, 2, "segredo")
    with pytest.raises(RoomError) as full:
        rooms.join(1, 3, "segredo")
    assert full.value.reason is RoomReason.FULL
    with pytest.raises(RoomError) as missing:
        rooms.join(99, 3, "")
    assert missing.value.reason is RoomReason.NOT_FOUND


def test_dominio_sair_transfere_dono_e_esvaziar_remove() -> None:
    rooms = Rooms()
    sala = _criar(rooms, 1)
    rooms.join(1, 2, "")
    saida = rooms.leave(1)
    assert saida is not None and not saida.removed and saida.new_master == 2
    assert sala.master == 2
    saida = rooms.leave(2)
    assert saida is not None and saida.removed
    assert rooms.get(1) is None and rooms.room_of(2) is None
    assert rooms.leave(2) is None


def test_dominio_pronto_inicio_e_expulsao() -> None:
    rooms = Rooms()
    sala = _criar(rooms, 1)
    rooms.join(1, 2, "")
    with pytest.raises(RoomError) as cedo:
        rooms.start(1, 0)
    assert cedo.value.reason is RoomReason.NOT_READY
    _, pronto = rooms.toggle_ready(2, 3)
    assert pronto and sala.members[2].morats == 3
    rooms.start(1, 0)
    assert sala.state == ROOM_PLAYING
    with pytest.raises(RoomError) as tarde:
        rooms.join(1, 4, "")
    assert tarde.value.reason is RoomReason.STARTED


def test_dominio_so_o_dono_expulsa_e_nao_expulsa_a_si_mesmo() -> None:
    rooms = Rooms()
    _criar(rooms, 1)
    rooms.join(1, 2, "")
    with pytest.raises(RoomError) as nao_dono:
        rooms.expel(2, 0)
    assert nao_dono.value.reason is RoomReason.NOT_OWNER
    with pytest.raises(RoomError) as si_mesmo:
        rooms.expel(1, 0)
    assert si_mesmo.value.reason is RoomReason.NO_SUCH_PLAYER
    expulso = rooms.expel(1, 1)
    assert expulso.guid == 2 and rooms.room_of(2) is None
