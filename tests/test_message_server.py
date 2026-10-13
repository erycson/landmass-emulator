import asyncio
import contextlib
import re
import struct
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from landmass_emu.app import message_server, open_accounts
from landmass_emu.domain.account import hash_token
from landmass_emu.domain.session_keys import MemorySessionKeyRegistry
from landmass_emu.net.framing import encode_frame, read_frame
from landmass_emu.net.server import start_service
from landmass_emu.protocol.header import MESSAGE_NET_CODE, pack_header, unpack_header
from landmass_emu.protocol.message import MsLoginIn, MsOp
from landmass_emu.settings import Settings

TOKEN = "0123456789abcdef0123456789abcdef"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
        bind_host="127.0.0.1",
        message_port=0,
    )


class Client:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.reader = reader
        self.writer = writer

    async def send(self, opcode: int, payload: bytes = b"") -> None:
        self.writer.write(encode_frame(pack_header(opcode, MESSAGE_NET_CODE) + payload))
        await self.writer.drain()

    async def recv(self) -> tuple[int, bytes]:
        async with asyncio.timeout(2):
            body = await read_frame(self.reader)
        assert body is not None
        header, payload = unpack_header(body)
        return header.opcode, payload

    async def assert_silencio(self) -> None:
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.3):
                await read_frame(self.reader)


@asynccontextmanager
async def _connect(server: asyncio.Server) -> AsyncIterator[Client]:
    port = server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        yield Client(reader, writer)
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()


async def test_sequencia_de_login_ate_lista_de_canais(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        await accounts.create("fulano", "Fulano", hash_token(TOKEN))

    registro = MemorySessionKeyRegistry()
    async with message_server(settings, registro) as server, _connect(server) as c:
        await c.send(MsOp.LOGIN, MsLoginIn(login_num=TOKEN).pack())
        op, body = await c.recv()
        assert op == MsOp.LOGIN_OUT and struct.unpack_from("<i", body, 4) == (0,)

        await c.send(MsOp.REGISTER)
        op, body = await c.recv()
        assert op == MsOp.REGISTER_OUT and struct.unpack_from("<i", body, 0x48) == (0,)
        assert re.fullmatch(rb"[0-9a-f]{32}\0", body[0x25:0x46])

        await c.send(MsOp.IN_MESSAGE_SERVER)
        op, body = await c.recv()
        assert op == MsOp.IN_MESSAGE_SERVER_OUT
        assert struct.unpack_from("<i", body, 0) == (0,)
        assert body[4:].split(b"\0", 1)[0] == b"Fulano"

        await c.send(MsOp.GET_CHANNEL_SERVER_INFO)
        op, body = await c.recv()
        assert op == MsOp.GET_CHANNEL_SERVER_OUT and body[0] >= 1
        entry = body[2:74]
        assert struct.unpack_from("<H", entry, 0) == (1,)
        assert struct.unpack_from("<HHHH", entry, 0x0C) == (100, 0, 0, settings.channel_port)
        assert entry[0x14:].split(b"\0", 1)[0] == b"127.0.0.1"
        assert entry[0x24:].split(b"\0", 1)[0] == b"Canal 1"


async def test_sem_login_nao_responde_e_opcode_desconhecido_nao_derruba(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        await accounts.create("fulano", "Fulano", hash_token(TOKEN))

    async with (
        message_server(settings, MemorySessionKeyRegistry()) as server,
        _connect(server) as c,
    ):
        await c.send(MsOp.GET_CHANNEL_SERVER_INFO)
        await c.send(182, b"\x01\x02")
        await c.send(MsOp.HEARTBEAT)
        await c.send(MsOp.LOGIN, b"\x01")  # payload curto: ignorado
        await c.send(MsOp.LOGIN, MsLoginIn(login_num=TOKEN).pack())
        op, body = await c.recv()
        assert op == MsOp.LOGIN_OUT and struct.unpack_from("<i", body, 4) == (0,)

        await c.send(182, b"\x01\x02")
        await c.send(MsOp.GET_CHANNEL_SERVER_INFO)
        op, _ = await c.recv()
        assert op == MsOp.GET_CHANNEL_SERVER_OUT


async def test_token_invalido_mantem_conexao_sem_login(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        await accounts.create("fulano", "Fulano", hash_token(TOKEN))

    async with (
        message_server(settings, MemorySessionKeyRegistry()) as server,
        _connect(server) as c,
    ):
        await c.send(MsOp.LOGIN, MsLoginIn(login_num="f" * 32).pack())
        op, body = await c.recv()
        assert op == MsOp.LOGIN_OUT and struct.unpack_from("<i", body, 4) == (-160,)
        await c.send(MsOp.GET_CHANNEL_SERVER_INFO)
        await c.assert_silencio()


async def test_sem_trafego_desconecta(tmp_path: Path) -> None:
    server = await start_service(
        "127.0.0.1", 0, net_code=MESSAGE_NET_CODE, router={}, recv_timeout=0.2
    )
    port = server.sockets[0].getsockname()[1]
    async with server:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        async with asyncio.timeout(5):
            assert await reader.read() == b""
        writer.close()
