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
    CsSendMessageIn,
    CsSendMessageOut,
)


def test_in_channel_server_in_le_login_num_de_33_bytes() -> None:
    payload = b"0123456789abcdef0123456789abcdef" + b"\0"
    assert CsInChannelServerIn.unpack(payload) == CsInChannelServerIn("0123456789abcdef" * 2)
    assert CsInChannelServerIn.unpack(payload + b"\x07\x07").login_num == "0123456789abcdef" * 2


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
    raw = CsChannelPlayer(
        client_guid=0x01020304,
        at04=0x11,
        at08=0x12,
        at0c=0x13,
        at10=0x14,
        at14=0x15,
        at18=0x21,
        at19=0x22,
        at1a=0x23,
        at1c=0x31,
        at20=0x32,
        at24=0x41,
    ).pack()
    assert len(raw) == 40
    assert raw[0:4] == b"\x04\x03\x02\x01"
    assert raw[4] == 0x11 and raw[8] == 0x12 and raw[12] == 0x13
    assert raw[16] == 0x14 and raw[20] == 0x15
    assert raw[24] == 0x21 and raw[25] == 0x22 and raw[26] == 0x23
    assert raw[27] == 0 and raw[37:40] == b"\0\0\0"
    assert raw[28] == 0x31 and raw[32] == 0x32
    assert raw[36] == 0x41


def test_in_channel_out_e_o_proprio_registro() -> None:
    player = CsChannelPlayer(client_guid=9)
    assert CsInChannelOut(player).pack() == player.pack()
    assert CsInChannelOut.opcode == CsOp.IN_CHANNEL_OUT


def test_lista_de_jogadores_contagem_e_stride_de_40() -> None:
    a = CsChannelPlayer(client_guid=1, at24=5)
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
    assert CsChannelInfoOut().pack() == b"\x01"
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
