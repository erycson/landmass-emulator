import asyncio
from pathlib import Path

import pytest

from landmass_emu.net.framing import FrameError, encode_frame, read_frame
from landmass_emu.protocol.header import MESSAGE_NET_CODE, Header, pack_header, unpack_header
from landmass_emu.protocol.message import MsLoginIn, MsOp

FIXTURES = Path(__file__).parent / "fixtures"


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
    frames = await _frames((FIXTURES / "ms_login_guid_1.bin").read_bytes())
    headers = [unpack_header(f)[0] for f in frames]
    assert headers[0] == Header(MsOp.LOGIN, MESSAGE_NET_CODE)
    assert all(h == Header(MsOp.HEARTBEAT, MESSAGE_NET_CODE) for h in headers[1:])
    assert len(frames) == 7


@pytest.mark.parametrize(
    ("fixture", "guid"),
    [("ms_login_guid_1.bin", "1"), ("ms_login_guid_developerguid.bin", "developerguid")],
)
async def test_ms_login_in_da_captura(fixture: str, guid: str) -> None:
    [login, *_] = await _frames((FIXTURES / fixture).read_bytes())
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
