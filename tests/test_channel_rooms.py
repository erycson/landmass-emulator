"""Salas: codec com offsets conferidos nos bytes (tools/re/rooms.md) e regras do domínio em
memória."""

import struct

import pytest

from landmass_emu.domain.rooms import (
    ROOM_PLAYER_SLOTS,
    ROOM_PLAYING,
    ROOM_WAITING,
    RoomError,
    RoomReason,
    Rooms,
)
from landmass_emu.protocol.channel import (
    ROOM_HEAD_SIZE,
    ROOM_INFO_SIZE,
    ROOM_RECORD_SIZE,
    ROOM_SLOTS,
    CsChangeRoomMasterOut,
    CsChangeRoomPropertyIn,
    CsChangeRoomPropertyOut,
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
    CsInviteResultOut,
    CsOp,
    CsOutRoomOut,
    CsPlayerDetailOut,
    CsReadyGameIn,
    CsReadyGameOut,
    CsRefreshRoomListIn,
    CsRefreshRoomListOut,
    CsRemoveRoomOut,
    CsRoom,
    CsRoomEntryOut,
    CsRoomExpelIn,
    CsRoomInfoOut,
    CsRoomInviteAnswerIn,
    CsRoomInviteIn,
    CsRoomInviteOut,
    CsRoomPlayer,
    CsRoomPlayerInfoOut,
    CsStartGameOut,
)
from landmass_emu.protocol.message import cfield, cstr


def _sala(**kw: object) -> CsRoom:
    base: dict[str, object] = {
        "room_id": 7,
        "name": "Sala",
        "has_password": False,
        "state": ROOM_WAITING,
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
    # Hexdump do cliente real: nome padrão da UI, sem senha, lixo de pilha após os NULs.
    payload = bytes.fromhex(
        "00005669766572206f75206d6f727265722e2e2e20497374"
        "6f20e920612071756573 74e36f2e0003c9981a0048ce151c".replace(" ", "")
        + "a8931a000900357c60941a00781a0310"
        + "6094200002180a105000"
    )
    assert len(payload) == 74
    req = CsCreateRoomIn.unpack(payload)
    name = "Viver ou morrer... Isto é a questão."
    assert req == CsCreateRoomIn(name, "", 0x20, 0, 0, 24, 2, 10, 80)


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
    raw = _sala(has_password=True, name="Sala Azul", scale=0x21).pack()
    assert len(raw) == ROOM_RECORD_SIZE == 612
    assert struct.unpack_from("<i", raw, 0x00) == (7,)  # chave de busca de 302, 312, 322...
    assert cstr(raw[0x04:0x37]) == "Sala Azul"  # char[51], de @4 até @0x36
    assert raw[0x04 + 9] == 0  # NUL depois do nome
    assert raw[0x37] == 1  # senha (bool `password` de LM_ROOM_INFO)
    assert raw[0x38] == 0  # estado: espera (RS_WAITING = 0 em Core.u)
    assert raw[0x39] == 2  # modo de jogo
    assert raw[0x3A] == 3  # times
    assert raw[0x3B] == 1  # jogadores (conta o dono)
    assert raw[0x3D] == 4  # máximo
    assert raw[0x3E] == 1  # aberta
    assert struct.unpack_from("<h", raw, 0x40) == (9,)  # mapa
    assert struct.unpack_from("<h", raw, 0x44) == (50,)  # limite de pontos
    assert raw[0x46] == 10  # limite de tempo
    assert raw[0x47] == 0x21  # escala (game_scale)
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
    raw = CsRoomInfoOut(_sala(limit_time=10, limit_score=50, scale=0x21)).pack()
    assert len(raw) == ROOM_INFO_SIZE == 0x38
    assert struct.unpack_from("<h", raw, 0x00) == (50,)  # limite de pontos (node+0x54)
    assert raw[0x02] == 10  # limite de tempo (node+0x56)
    assert raw[0x03] == 0x21  # escala (node+0x57)
    assert struct.unpack_from("<i", raw, 0x08) == (0x0102,)  # dono (node+0x5c)
    assert struct.unpack_from("<i", raw, 0x0C) == (7,)  # chave de busca (body+0xc)
    assert raw[0x10] == 0 and raw[0x11] == 2 and raw[0x12] == 3 and raw[0x13] == 4  # espera
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


def test_jogador_de_sala_tem_o_nick_e_o_total_exp_do_registro_de_151() -> None:
    entrada = CsRoomPlayer(client_guid=5, slot=0, ready=False, morats=0, nick="Ana").pack()
    assert len(entrada) == 48
    assert entrada[0x08:0x18] == b"Ana" + bytes(13)
    assert entrada[0x18:0x28] == bytes(16)  # campos sem valor no lobby
    com_exp = CsRoomPlayer(client_guid=5, slot=0, ready=False, morats=0, total_exp=1234).pack()
    assert struct.unpack_from("<i", com_exp, 0x04) == (1234,)


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


def test_411_flags_e_campos_no_corpo_de_10_bytes() -> None:
    payload = struct.pack("<BxHBBBBH", 0x07, 9, 2, 3, 4, 10, 50)
    assert len(payload) == 10
    assert CsChangeRoomPropertyIn.unpack(payload) == CsChangeRoomPropertyIn(
        0x07, 9, 2, 3, 4, 10, 50
    )
    with pytest.raises(ValueError):
        CsChangeRoomPropertyIn.unpack(bytes(9))


def test_412_so_os_campos_marcados_e_mascara_no_byte_4() -> None:
    raw = CsChangeRoomPropertyOut(
        7, map_num=9, game_mode=2, team_count=3, max_player=4, limit_time=10, limit_score=50
    ).pack()
    assert len(raw) == 16
    assert struct.unpack_from("<i", raw, 0) == (7,)
    assert raw[4] == 0x1F  # MAP | MODE | LIMIT_PLAYER | LIMIT_SCORE | LIMIT_TIME
    assert struct.unpack_from("<h", raw, 6) == (9,)
    assert raw[8:10] == bytes((2, 3))
    assert raw[0xA] == 4 and raw[0xB] == 10
    assert struct.unpack_from("<h", raw, 0xC) == (50,)
    assert raw[0xE] == 0 and raw[0xF] == 0  # OPEN e STATE desligados
    assert CsChangeRoomPropertyOut.opcode == CsOp.CHANGE_ROOM_PROPERTY_OUT == 412


def test_412_estado_e_aberta_usam_seus_bits() -> None:
    estado = CsChangeRoomPropertyOut(7, state=2).pack()
    assert estado[4] == 0x20 and estado[0xF] == 2
    aberta = CsChangeRoomPropertyOut(7, is_open=False).pack()
    assert aberta[4] == 0x40 and aberta[0xE] == 0


def test_412_modo_exige_modo_e_times_juntos() -> None:
    with pytest.raises(ValueError):
        CsChangeRoomPropertyOut(7, game_mode=2).pack()


def test_slot_420_421_e_pronto_401() -> None:
    assert CsChangeRoomSlotIn.unpack(b"\x03") == CsChangeRoomSlotIn(3)
    with pytest.raises(ValueError):
        CsChangeRoomSlotIn.unpack(b"")
    assert CsChangeRoomSlotOut(0x11, 3).pack() == struct.pack("<iB3x", 0x11, 3)
    assert CsChangeRoomSlotOut.opcode == CsOp.CHANGE_ROOM_SLOT_OUT == 421
    assert CsReadyGameIn.unpack(b"\x05") == CsReadyGameIn(5)
    with pytest.raises(ValueError):
        CsReadyGameIn.unpack(b"")


def test_451_expulsao_pelo_nick_com_pad_no_inicio() -> None:
    raw = CsRoomExpelIn("Ana").pack()
    assert len(raw) == 18
    assert raw[0] == 0  # @0 não é preenchido pelo cliente
    assert cstr(raw[1:18]) == "Ana"
    assert CsRoomExpelIn.unpack(raw) == CsRoomExpelIn("Ana")
    with pytest.raises(ValueError):
        CsRoomExpelIn.unpack(bytes(17))


def test_700_expulsao_do_console_kind_e_nick() -> None:
    raw = CsExpelPlayerIn(0x21, "Ana").pack()
    assert len(raw) == 18
    assert raw[0] == 0x21
    assert cstr(raw[1:18]) == "Ana"
    assert CsExpelPlayerIn.unpack(raw) == CsExpelPlayerIn(0x21, "Ana")
    with pytest.raises(ValueError):
        CsExpelPlayerIn.unpack(bytes(17))
    assert CsExpelPlayerOut().pack() == bytes(4)
    assert CsOp.EXPEL_PLAYER == 700
    assert CsExpelPlayerOut.opcode == CsOp.EXPEL_PLAYER_OUT == 701


def test_461_convite_pedido_com_nick_de_17_bytes() -> None:
    assert CsRoomInviteIn.unpack(cfield("Bia", 17)) == CsRoomInviteIn("Bia")
    with pytest.raises(ValueError):
        CsRoomInviteIn.unpack(bytes(16))
    assert CsOp.ROOM_INVITE == 461


def test_462_resposta_ao_convidador_com_i32_e_cerr() -> None:
    assert CsInviteResultOut(0).pack() == bytes(4)
    assert CsInviteResultOut(-2460).pack() == struct.pack("<i", -2460)
    assert CsInviteResultOut.opcode == CsOp.ROOM_INVITE_OUT == 462


def test_463_convite_ao_convidado_com_sala_e_nick_de_quem_convida() -> None:
    raw = CsRoomInviteOut(7, "Ana").pack()
    assert len(raw) == 21
    assert struct.unpack_from("<i", raw, 0) == (7,)
    assert cstr(raw[4:21]) == "Ana"
    assert CsRoomInviteOut.opcode == CsOp.ROOM_INVITE_NOTIFY == 463


def test_471_resposta_ao_convite_com_aceite_no_byte_4() -> None:
    raw = CsRoomInviteAnswerIn(7, True).pack()
    assert raw == struct.pack("<iB3x", 7, 1)
    assert CsRoomInviteAnswerIn.unpack(raw) == CsRoomInviteAnswerIn(7, True)
    recusa = struct.pack("<iB3x", 7, 0)
    assert CsRoomInviteAnswerIn.unpack(recusa) == CsRoomInviteAnswerIn(7, False)
    with pytest.raises(ValueError):
        CsRoomInviteAnswerIn.unpack(bytes(4))
    assert CsOp.ROOM_INVITE_ANSWER == 471


def test_549_entrada_de_quem_chegou_e_o_registro_de_317() -> None:
    jogador = CsRoomPlayer(
        client_guid=0x22, slot=1, ready=False, morats=0, nick="Bia", total_exp=900
    )
    raw = CsRoomEntryOut(jogador).pack()
    assert raw == jogador.pack()
    assert len(raw) == 48
    assert struct.unpack_from("<i", raw, 0x04) == (900,)
    assert raw[0x28] == 1  # slot
    assert CsRoomEntryOut.opcode == CsOp.ROOM_ENTRY_OUT == 549


def test_543_detalhe_do_jogador_offsets() -> None:
    raw = CsPlayerDetailOut(
        "Ana",
        rank=1,
        games=2,
        wins=3,
        losses=4,
        kills=5,
        deaths=6,
        headshots=7,
        total_exp=8,
        nest=9,
        clan_mark=10,
        clan="Gx",
    ).pack()
    assert len(raw) == 0x3C + 17
    assert cstr(raw[0:0x14]) == "Ana"
    assert struct.unpack_from("<8i", raw, 0x14) == (1, 2, 3, 4, 5, 6, 7, 8)
    assert raw[0x34] == 9  # nest
    assert struct.unpack_from("<i", raw, 0x38) == (10,)  # clan_mark
    assert cstr(raw[0x3C:]) == "Gx"
    assert CsPlayerDetailOut.opcode == CsOp.PLAYER_DETAIL_OUT == 543


def test_erro_envelope_de_404_com_opcode_real_e_codigo() -> None:
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
    assert sala.members[1].slot == 0 and not sala.members[1].ready  # dono sem pronto (D77)
    rooms.join(1, 2, "")
    assert rooms.room_of(2) is sala and sala.members[2].slot == 1


def test_estados_da_sala_seguem_rs_do_core() -> None:
    # RS_WAITING e RS_PLAYING em Core.u são 0 e 1 (UConst " \t0" e " \t1"). 1 é jogando.
    assert (ROOM_WAITING, ROOM_PLAYING) == (0, 1)


def test_dominio_mudar_grupo_vai_ao_primeiro_slot_livre_do_grupo() -> None:
    rooms = Rooms()
    sala = rooms.create(
        1,
        name="Sala",
        password="",
        scale=0,
        game_mode=1,
        map_num=1,
        max_player=4,
        team_count=2,
        limit_time=10,
        limit_score=10,
    )
    rooms.join(1, 2, "")  # slot 1, grupo 1
    rooms.join(1, 3, "")  # slot 2, grupo 0
    with pytest.raises(RoomError) as exc:
        rooms.change_slot(2, 0)  # grupo 0 tem slot 0 (dono) e 2 (guid 3): sem vaga
    assert exc.value.reason is RoomReason.NO_TEAM_SLOT
    rooms.leave(3)
    rooms.change_slot(2, 0)  # agora o slot 2 está livre no grupo 0
    assert sala.members[2].slot == 2
    rooms.change_slot(2, 1)  # volta ao primeiro slot livre do grupo 1, o slot 1
    assert sala.members[2].slot == 1
    with pytest.raises(RoomError) as exc:
        rooms.change_slot(2, 7)  # grupo que não existe
    assert exc.value.reason is RoomReason.NO_TEAM_SLOT


def test_dominio_senha_cheia_e_sala_inexistente() -> None:
    rooms = Rooms()
    _criar(rooms, 1, senha="segredo", max_player=2)
    with pytest.raises(RoomError) as wrong:
        rooms.join(1, 2, "errada")
    assert wrong.value.reason is RoomReason.WRONG_PASSWORD
    rooms.join(1, 2, "segredo")
    # Sem vaga de jogador, quem entra vai para o slot de espectador (D197); o teto é 2.
    assert rooms.join(1, 3, "segredo").members[3].slot == ROOM_PLAYER_SLOTS
    rooms.join(1, 4, "segredo")
    with pytest.raises(RoomError) as full:
        rooms.join(1, 5, "segredo")
    assert full.value.reason is RoomReason.FULL
    with pytest.raises(RoomError) as missing:
        rooms.join(99, 9, "")
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


def test_dominio_inicio_solo_so_com_bots() -> None:
    sozinho = Rooms()
    _criar(sozinho, 1)
    with pytest.raises(RoomError) as erro:
        sozinho.start(1, 0)
    assert erro.value.reason is RoomReason.NOT_READY
    com_bots = Rooms(solo=True)
    sala = _criar(com_bots, 1)
    com_bots.start(1, 0)
    assert sala.state == ROOM_PLAYING and sala.in_game == {1}


def test_dominio_pronto_inicio_e_entrada_tardia() -> None:
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
        rooms.expel(1, 1)
    assert si_mesmo.value.reason is RoomReason.NO_SUCH_PLAYER
    expulso = rooms.expel(1, 2)
    assert expulso.guid == 2 and rooms.room_of(2) is None


def test_dominio_configurar_so_o_dono_com_sala_esperando() -> None:
    rooms = Rooms()
    sala = _criar(rooms, 1)
    rooms.join(1, 2, "")
    with pytest.raises(RoomError) as nao_dono:
        rooms.configure(2, {"map_num": 5})
    assert nao_dono.value.reason is RoomReason.NOT_OWNER
    rooms.configure(1, {"map_num": 5, "limit_time": 3})
    assert sala.map_num == 5 and sala.limit_time == 3
    with pytest.raises(RoomError) as campo:
        rooms.configure(1, {"master": 9})
    assert campo.value.reason is RoomReason.BAD_SETTING
    with pytest.raises(RoomError) as pequena:
        rooms.configure(1, {"max_player": 1})  # já há dois jogadores
    assert pequena.value.reason is RoomReason.BAD_SETTING
    rooms.toggle_ready(2, 0)
    rooms.start(1, 0)
    with pytest.raises(RoomError) as tarde:
        rooms.configure(1, {"map_num": 6})
    assert tarde.value.reason is RoomReason.STARTED


def test_dominio_convite_fica_pendente_ate_o_aceite() -> None:
    rooms = Rooms()
    sala = _criar(rooms, 1)
    assert rooms.invite(1, 2) is sala
    assert rooms.accept_invite(2, sala.room_id) is sala
    assert rooms.room_of(2) is sala and sala.members[2].slot == 1
    rooms.invite(1, 3)
    with pytest.raises(RoomError) as outra:
        rooms.accept_invite(3, sala.room_id + 99)
    assert outra.value.reason is RoomReason.NOT_INVITED
    with pytest.raises(RoomError) as sem:
        rooms.accept_invite(3, sala.room_id)
    assert sem.value.reason is RoomReason.NOT_INVITED


def test_dominio_convite_recusado_e_restrito_ao_dono() -> None:
    rooms = Rooms()
    sala = _criar(rooms, 1, max_player=3)
    rooms.join(1, 2, "")
    with pytest.raises(RoomError) as nao_dono:
        rooms.invite(2, 3)
    assert nao_dono.value.reason is RoomReason.NOT_OWNER
    with pytest.raises(RoomError) as dentro:
        rooms.invite(1, 2)
    assert dentro.value.reason is RoomReason.ALREADY_IN_ROOM
    rooms.invite(1, 3)
    rooms.decline_invite(3)
    with pytest.raises(RoomError) as recusado:
        rooms.accept_invite(3, sala.room_id)
    assert recusado.value.reason is RoomReason.NOT_INVITED
