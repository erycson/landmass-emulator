import struct

import pytest

from landmass_emu.protocol.channel import (
    MAX_CHAT_TEXT,
    MAX_LOBBY_ENTRIES,
    CsChannelInfoOut,
    CsChannelPlayer,
    CsChannelPlayerInfoOut,
    CsChannelRoomInfoOut,
    CsHeartbeat,
    CsInChannelOut,
    CsInChannelServerIn,
    CsInChannelServerOut,
    CsOp,
    CsOutChannelOut,
    CsPlayerProperty,
    CsRefreshPlayerListIn,
    CsRefreshPlayerListOut,
    CsSendMessageIn,
    CsSendMessageOut,
)


def test_in_channel_server_in_le_session_key_de_33_bytes() -> None:
    payload = b"0123456789abcdef0123456789abcdef" + b"\0"
    assert CsInChannelServerIn.unpack(payload) == CsInChannelServerIn("0123456789abcdef" * 2)
    extra = CsInChannelServerIn.unpack(payload + b"\x07\x07")
    assert extra.session_key == "0123456789abcdef" * 2


def test_in_channel_server_in_chave_zerada_vira_string_vazia() -> None:
    assert CsInChannelServerIn.unpack(bytes(33)).session_key == ""


def test_in_channel_server_in_rejeita_payload_curto() -> None:
    with pytest.raises(ValueError):
        CsInChannelServerIn.unpack(b"x" * 32)


def test_in_channel_server_out_tamanho_e_offsets() -> None:
    raw = CsInChannelServerOut(client_guid=7, result=0).pack()
    assert len(raw) == 0xB0
    assert struct.unpack_from("<i", raw, 0x90) == (7,)
    assert struct.unpack_from("<i", raw, 0xA0) == (7,)
    assert raw[0x00:0x90] == bytes(0x90)
    assert raw[0x94:0xA0] == bytes(0x0C)
    assert raw[0xA4:0xA8] == bytes(4)
    assert struct.unpack_from("<i", raw, 0xA8) == (0,)
    assert struct.unpack_from("<i", raw, 0xAC) == (0,)


def test_in_channel_server_out_resultado_negativo_e_location() -> None:
    raw = CsInChannelServerOut(client_guid=0, result=-160, location=3).pack()
    assert struct.unpack_from("<i", raw, 0xA8) == (-160,)
    assert struct.unpack_from("<i", raw, 0xAC) == (3,)


def test_channel_player_tamanho_e_offsets() -> None:
    # Layout de re/layouts_f0.md §1.2 (registro de 151 e 121).
    raw = CsChannelPlayer(
        client_guid=0x01020304,
        nick="Ana",
        total_exp=0x11223344,
        unk18=0x21,
        vehicle_licence=0x22,
        access=0x23,
        clan=0x31,
        clan_mark=0x32,
        nest=0x41,
    ).pack()
    assert len(raw) == 40
    assert struct.unpack_from("<i", raw, 0x00) == (0x01020304,)
    assert struct.unpack_from("<i", raw, 0x04) == (0x11223344,)
    assert raw[0x08:0x18] == b"Ana" + bytes(13)  # char[16] NUL-padded
    assert raw[0x18] == 0x21 and raw[0x19] == 0x22 and raw[0x1A] == 0x23
    assert raw[0x1B] == 0
    assert struct.unpack_from("<i", raw, 0x1C) == (0x31,)
    assert struct.unpack_from("<i", raw, 0x20) == (0x32,)
    assert raw[0x24] == 0x41
    assert raw[0x25:0x28] == bytes(3)


def test_channel_player_nick_trunca_em_15_mais_nul() -> None:
    raw = CsChannelPlayer(client_guid=1, nick="A" * 20).pack()
    assert raw[0x08:0x18] == b"A" * 15 + b"\0"


def test_pedido_546_le_guids_e_limita_a_14() -> None:
    corpo = bytearray(64)
    struct.pack_into("<i", corpo, 0, 0)  # canal, ignorado
    corpo[4] = 2
    struct.pack_into("<ii", corpo, 8, 7, 8)
    assert CsRefreshPlayerListIn.unpack(bytes(corpo)).client_guids == (7, 8)
    corpo[4] = 20
    for i in range(14):
        struct.pack_into("<i", corpo, 8 + 4 * i, i + 1)
    assert CsRefreshPlayerListIn.unpack(bytes(corpo)).client_guids == tuple(range(1, 15))
    with pytest.raises(ValueError):
        CsRefreshPlayerListIn.unpack(bytes(7))


def test_resposta_548_cabecalho_e_entradas_de_20_bytes() -> None:
    raw = CsRefreshPlayerListOut(
        (CsPlayerProperty(7, total_exp=5, clan=6, clan_mark=7, nest=8), CsPlayerProperty(9))
    ).pack()
    assert len(raw) == 4 + 2 * 20
    assert raw[0] == 2 and raw[1:4] == bytes(3)
    assert struct.unpack_from("<iiii", raw, 4) == (7, 5, 6, 7)
    assert raw[4 + 16] == 8 and raw[4 + 17 : 4 + 20] == bytes(3)
    assert struct.unpack_from("<i", raw, 24) == (9,)
    assert CsRefreshPlayerListOut(()).pack() == bytes(4)
    assert CsRefreshPlayerListOut.opcode == CsOp.REFRESH_PLAYER_LIST_OUT == 548


def test_in_channel_out_e_o_proprio_registro() -> None:
    player = CsChannelPlayer(client_guid=9)
    assert CsInChannelOut(player).pack() == player.pack()
    assert CsInChannelOut.opcode == CsOp.IN_CHANNEL_OUT


def test_lista_de_jogadores_contagem_e_stride_de_40() -> None:
    a = CsChannelPlayer(client_guid=1, nest=5)
    b = CsChannelPlayer(client_guid=2)
    raw = CsChannelPlayerInfoOut((a, b)).pack()
    assert raw[0:2] == b"\x02\x00"
    assert len(raw) == 2 + 40 * 2
    assert struct.unpack_from("<i", raw, 2) == (1,)
    assert raw[2 + 36] == 5
    assert struct.unpack_from("<i", raw, 42) == (2,)


def test_lista_vazia_e_lista_grande_demais() -> None:
    assert CsChannelPlayerInfoOut(()).pack() == b"\x00\x00"
    players = (CsChannelPlayer(client_guid=1),) * (MAX_LOBBY_ENTRIES + 1)
    with pytest.raises(ValueError):
        CsChannelPlayerInfoOut(players).pack()


def test_channel_info_e_room_info_com_contagem_zero_ou_um() -> None:
    assert CsChannelInfoOut().pack() == b"\x01\x00"
    assert CsChannelInfoOut((10, 100)).pack() == b"\x02\x0a\x64"
    assert CsChannelRoomInfoOut().pack() == b"\x00\x00"


def test_heartbeat_corpo_vazio() -> None:
    assert CsHeartbeat().pack() == b""
    assert CsHeartbeat.opcode == CsOp.HEARTBEAT


def test_out_channel_out_tamanho_e_offsets() -> None:
    raw = CsOutChannelOut(client_guid=0x0A0B0C0D, message=2).pack()
    assert len(raw) == 8
    assert raw[0:4] == b"\x0d\x0c\x0b\x0a"
    assert raw[4] == 2
    assert raw[5:8] == b"\0\0\0"


def test_send_message_in_le_tipo_tamanho_e_texto() -> None:
    msg = CsSendMessageIn.unpack(bytes([4, 3]) + b"abc" + b"\x99")
    assert msg == CsSendMessageIn(msg_type=4, text=b"abc")


def test_send_message_in_rejeita_tamanho_inconsistente() -> None:
    with pytest.raises(ValueError):
        CsSendMessageIn.unpack(bytes([0, 5]) + b"abc")
    with pytest.raises(ValueError):
        CsSendMessageIn.unpack(bytes([0, MAX_CHAT_TEXT + 1]) + b"x" * (MAX_CHAT_TEXT + 1))
    with pytest.raises(struct.error):
        CsSendMessageIn.unpack(b"\x00")


def test_send_message_out_tamanho_e_offsets() -> None:
    raw = CsSendMessageOut(sender=9, msg_type=1, text=b"oi").pack()
    assert len(raw) == 8 + 2
    assert struct.unpack_from("<i", raw, 0) == (9,)
    assert raw[4] == 1
    assert raw[5] == 2
    assert raw[6:8] == b"\0\0"
    assert raw[8:10] == b"oi"


def test_send_message_out_rejeita_texto_longo() -> None:
    with pytest.raises(ValueError):
        CsSendMessageOut(sender=1, msg_type=0, text=b"x" * (MAX_CHAT_TEXT + 1)).pack()
