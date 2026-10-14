import asyncio
import struct

import pytest

from landmass_emu.net.framing import FrameError, encode_frame, read_frame
from landmass_emu.protocol.header import MESSAGE_NET_CODE, Header, pack_header, unpack_header
from landmass_emu.protocol.message import (
    LmRegisterInfo,
    LmServerInfo,
    MsGetChannelServerOut,
    MsInMessageServerOut,
    MsLoginIn,
    MsLoginOut,
    MsOp,
    MsRegisterOut,
    MsResult,
)

# Capturas reais do cliente: o MS_LOGIN (14 bytes de cabeçalho e GUID, mais lixo de pilha que o
# cliente manda no buffer) seguido de heartbeats (`02 00 4d 00`).
_HEARTBEAT = "02004d00"
CAPTURAS = {
    "guid_1": bytes.fromhex(
        "2e008d0c0000000000000000310000001ca71a0060246a76d16f8adafeffffff"
        "74a11a007f9569766400000000010000" + _HEARTBEAT * 6
    ),
    "guid_developerguid": bytes.fromhex(
        "2e008d0c0000000000000000646576656c6f7065726775696400aea0feffffff"
        "74a11a007f9569766400000000010000" + _HEARTBEAT * 24
    ),
}


def _reader(data: bytes) -> asyncio.StreamReader:
    r = asyncio.StreamReader()
    r.feed_data(data)
    r.feed_eof()
    return r


async def _frames(data: bytes) -> list[bytes]:
    r, out = _reader(data), []
    while (f := await read_frame(r)) is not None:
        out.append(f)
    return out


async def test_captura_real_login_e_heartbeats() -> None:
    frames = await _frames(CAPTURAS["guid_1"])
    headers = [unpack_header(f)[0] for f in frames]
    assert headers[0] == Header(MsOp.LOGIN, MESSAGE_NET_CODE)
    assert all(h == Header(MsOp.HEARTBEAT, MESSAGE_NET_CODE) for h in headers[1:])
    assert len(frames) == 7


@pytest.mark.parametrize(
    ("fixture", "guid"),
    [("guid_1", "1"), ("guid_developerguid", "developerguid")],
)
async def test_ms_login_in_da_captura(fixture: str, guid: str) -> None:
    [login, *_] = await _frames(CAPTURAS[fixture])
    _, payload = unpack_header(login)
    msg = MsLoginIn.unpack(payload)
    assert msg == MsLoginIn(login_num=guid)


def test_ms_login_in_ida_e_volta_com_usuario() -> None:
    msg = MsLoginIn(login_num="", user_id="fulano", password="segredo")
    assert MsLoginIn.unpack(msg.pack()) == msg


def test_ms_login_in_rejeita_tamanhos_inconsistentes() -> None:
    bad = MsLoginIn(login_num="x").pack()
    bad = (999).to_bytes(4, "little") + bad[4:]
    with pytest.raises(ValueError):
        MsLoginIn.unpack(bad)


def test_header_ida_e_volta() -> None:
    assert pack_header(MsOp.HEARTBEAT, MESSAGE_NET_CODE) == b"\x4d\x00"
    assert unpack_header(pack_header(131, 13) + b"xy") == (Header(131, 13), b"xy")


async def test_frame_eof_no_meio_e_tamanho_maximo() -> None:
    with pytest.raises(FrameError):
        await read_frame(_reader(b"\x05"))
    with pytest.raises(FrameError):
        encode_frame(b"\0" * 65001)
    assert await _frames(encode_frame(b"ab") + encode_frame(b"")) == [b"ab", b""]


def test_login_out_tamanho_e_resultado() -> None:
    raw = MsLoginOut(MsResult.INVALID_PASSWORD).pack()
    assert len(raw) == 8
    assert raw[0] == 0 and raw[1:4] == b"\0\0\0"
    assert struct.unpack_from("<i", raw, 4) == (-160,)
    assert MsLoginOut.opcode == MsOp.LOGIN_OUT


def test_register_out_tamanho_e_offsets() -> None:
    raw = MsRegisterOut().pack()
    assert len(raw) == 0x4C
    assert raw[0x00:0x25] == bytes(0x25)
    assert raw[0x25:0x46] == bytes(0x21)
    assert raw[0x46:0x48] == b"\0\0"
    assert struct.unpack_from("<i", raw, 0x48) == (0,)


def test_register_out_session_key_em_0x25_char33() -> None:
    chave = "0123456789abcdef" * 2
    raw = MsRegisterOut(session_key=chave, result=7).pack()
    assert len(raw) == 0x4C
    assert raw[0x25:0x46] == chave.encode() + b"\0"
    assert raw[0x46:0x48] == b"\0\0"
    assert struct.unpack_from("<i", raw, 0x48) == (7,)


def test_register_out_opcoes_na_ordem_do_layout() -> None:
    raw = MsRegisterOut(options=LmRegisterInfo(background=1, weapon_1=2, screenshot=9)).pack()
    assert raw[0] == 1 and raw[7] == 2 and raw[36] == 9


def test_lm_register_info_ida_e_volta_e_tamanho_37() -> None:
    opcoes = LmRegisterInfo(mouse_sensitivity=5, alt_fire=7, speech_menu_3=8)
    raw = opcoes.pack()
    assert len(raw) == 37
    assert raw[5] == 5 and raw[22] == 7 and raw[32] == 8
    assert LmRegisterInfo.unpack(raw) == opcoes
    assert LmRegisterInfo.unpack(raw + b"\x09") == opcoes


def test_lm_register_info_payload_curto_levanta_struct_error() -> None:
    with pytest.raises(struct.error):
        LmRegisterInfo.unpack(bytes(36))


def test_in_message_server_out_offsets() -> None:
    raw = MsInMessageServerOut(MsResult.OK, "Fulano").pack()
    assert len(raw) == 0x1C
    assert struct.unpack_from("<i", raw, 0) == (0,)
    assert raw[4:10] == b"Fulano" and raw[10] == 0
    assert raw[0x15:0x18] == b"\0\0\0"
    assert struct.unpack_from("<i", raw, 0x18) == (0,)


def test_nickname_truncado_em_16_com_nul() -> None:
    raw = MsInMessageServerOut(0, "A" * 16).pack()
    assert raw[4:20] == b"A" * 16 and raw[20] == 0
    raw = MsInMessageServerOut(0, "B" * 40).pack()
    assert raw[4:20] == b"B" * 16 and raw[20] == 0


def test_nickname_cp1252() -> None:
    raw = MsInMessageServerOut(0, "João").pack()
    assert raw[4:8] == "João".encode("cp1252") and raw[8] == 0


def test_server_info_tamanho_e_offsets() -> None:
    raw = LmServerInfo(
        server_id=3,
        service_port=7314,
        max_client_count=100,
        server_name="Canal 1",
        service_address="127.0.0.1",
    ).pack()
    assert len(raw) == 72
    assert struct.unpack_from("<H", raw, 0) == (3,)
    assert raw[2:6] == b"\0\0\0\0"
    assert struct.unpack_from("<i", raw, 8) == (0,)
    assert struct.unpack_from("<HHHH", raw, 0x0C) == (100, 0, 0, 7314)
    assert raw[0x14 : 0x14 + 9] == b"127.0.0.1" and raw[0x14 + 9] == 0
    assert raw[0x24 : 0x24 + 7] == b"Canal 1" and raw[0x24 + 7] == 0


def test_server_info_leva_o_channel_mode_no_byte_4() -> None:
    # 6 é CM_CLAN (Core.u): com ele o cliente entra na tela de clã (XInterface L21591).
    raw = LmServerInfo(
        server_id=2,
        service_port=7314,
        max_client_count=100,
        server_name="Clã",
        service_address="127.0.0.1",
        channel_mode=6,
    ).pack()
    assert raw[4] == 6
    assert LmServerInfo(1, 1, 1, "", "").pack()[4] == 0


def test_server_info_trunca_endereco_em_15_e_nome_em_35() -> None:
    raw = LmServerInfo(
        server_id=1,
        service_port=1,
        max_client_count=1,
        server_name="N" * 50,
        service_address="1" * 50,
    ).pack()
    assert raw[0x14:0x23] == b"1" * 15 and raw[0x23] == 0
    assert raw[0x24:0x47] == b"N" * 35 and raw[0x47] == 0


def test_get_channel_server_out_count_brandom_e_entradas() -> None:
    info = LmServerInfo(
        server_id=1,
        service_port=7314,
        max_client_count=100,
        server_name="Canal 1",
        service_address="127.0.0.1",
    )
    raw = MsGetChannelServerOut((info, info)).pack()
    assert len(raw) == 2 + 72 * 2
    assert raw[0] == 2 and raw[1] == 0
    assert raw[2:74] == info.pack() and raw[74:146] == info.pack()
    assert MsGetChannelServerOut(()).pack() == b"\x00\x00"
    assert MsGetChannelServerOut((), b_random=True).pack() == b"\x00\x01"
