import asyncio
import contextlib
import struct
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from landmass_emu.app import channel_server, message_server, open_accounts
from landmass_emu.domain.account import hash_token
from landmass_emu.net.framing import encode_frame, read_frame
from landmass_emu.net.server import start_service
from landmass_emu.protocol.channel import CsHeartbeat, CsOp
from landmass_emu.protocol.header import (
    CHANNEL_NET_CODE,
    MESSAGE_NET_CODE,
    pack_header,
    unpack_header,
)
from landmass_emu.protocol.message import MsLoginIn, MsOp
from landmass_emu.settings import Settings

TOKEN_ANA = "0123456789abcdef0123456789abcdef"
TOKEN_BIA = "fedcba9876543210fedcba9876543210"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
        bind_host="127.0.0.1",
        message_port=0,
        channel_port=0,
    )


def _login_payload(token: str) -> bytes:
    """CS_IN_CHANNEL_SERVER_IN: login_num em char[33]."""
    return token.encode("ascii").ljust(33, b"\0")


class Client:
    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, net_code: int
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.net_code = net_code

    async def send(self, opcode: int, payload: bytes = b"") -> None:
        self.writer.write(encode_frame(pack_header(opcode, self.net_code) + payload))
        await self.writer.drain()

    async def recv(self) -> tuple[int, bytes]:
        async with asyncio.timeout(2):
            body = await read_frame(self.reader)
        assert body is not None
        header, payload = unpack_header(body)
        return header.opcode, payload

    async def expect(self, opcode: int) -> bytes:
        op, body = await self.recv()
        assert op == opcode, f"esperado opcode {opcode}, veio {op}"
        return body

    async def assert_silencio(self) -> None:
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.3):
                await read_frame(self.reader)


@asynccontextmanager
async def _connect(server: asyncio.Server, net_code: int) -> AsyncIterator[Client]:
    port = server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        yield Client(reader, writer, net_code)
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()


async def _entra_no_canal(c: Client, token: str, guid: int) -> None:
    """100 → 101/111, depois 120 → 151/141/121. Confere o id nos offsets do cliente."""
    await c.send(CsOp.IN_CHANNEL_SERVER, _login_payload(token))
    body = await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
    assert struct.unpack_from("<i", body, 0x90) == (guid,)
    assert struct.unpack_from("<i", body, 0xA0) == (guid,)
    assert struct.unpack_from("<i", body, 0xA8) == (0,)
    assert await c.expect(CsOp.CHANNEL_INFO_OUT) == b"\x01"
    await c.send(CsOp.IN_CHANNEL)
    await c.expect(CsOp.CHANNEL_PLAYER_INFO_OUT)
    await c.expect(CsOp.CHANNEL_ROOM_INFO_OUT)
    body = await c.expect(CsOp.IN_CHANNEL_OUT)
    assert struct.unpack_from("<i", body, 0) == (guid,)


async def test_dois_clientes_se_veem_no_lobby(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana = await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))
        bia = await accounts.create("bia", "Bia", hash_token(TOKEN_BIA))

    async with message_server(settings) as msg, channel_server(settings) as ch:
        async with _connect(msg, MESSAGE_NET_CODE) as m:
            await m.send(MsOp.LOGIN, MsLoginIn(login_num=TOKEN_ANA).pack())
            assert struct.unpack_from("<i", await m.expect(MsOp.LOGIN_OUT), 4) == (0,)

        async with (
            _connect(ch, CHANNEL_NET_CODE) as a,
            _connect(ch, CHANNEL_NET_CODE) as b,
        ):
            await _entra_no_canal(a, TOKEN_ANA, ana.id)

            # B: a lista já traz A; A recebe o broadcast de B.
            await b.send(CsOp.IN_CHANNEL_SERVER, _login_payload(TOKEN_BIA))
            await b.expect(CsOp.IN_CHANNEL_SERVER_OUT)
            await b.expect(CsOp.CHANNEL_INFO_OUT)
            await b.send(CsOp.IN_CHANNEL)
            lista = await b.expect(CsOp.CHANNEL_PLAYER_INFO_OUT)
            assert lista[0:2] == b"\x01\x00"
            assert struct.unpack_from("<i", lista, 2) == (ana.id,)
            await b.expect(CsOp.CHANNEL_ROOM_INFO_OUT)
            assert struct.unpack_from("<i", await b.expect(CsOp.IN_CHANNEL_OUT), 0) == (bia.id,)
            assert struct.unpack_from("<i", await a.expect(CsOp.IN_CHANNEL_OUT), 0) == (bia.id,)

            # Chat de B chega a A e a B (remetente incluído).
            await b.send(CsOp.SEND_MESSAGE, bytes([0, 2]) + b"oi")
            for c in (a, b):
                body = await c.expect(CsOp.SEND_MESSAGE_OUT)
                assert struct.unpack_from("<i", body, 0) == (bia.id,)
                assert body[4] == 0 and body[5] == 2 and body[8:10] == b"oi"

            # Chat de A, com tipo 1.
            await a.send(CsOp.SEND_MESSAGE, bytes([1, 3]) + b"ola")
            for c in (a, b):
                body = await c.expect(CsOp.SEND_MESSAGE_OUT)
                assert struct.unpack_from("<i", body, 0) == (ana.id,)
                assert body[4] == 1 and body[8:11] == b"ola"

            # Saída voluntária: B recebe a própria saída; A recebe a de B.
            await b.send(CsOp.OUT_CHANNEL)
            for c in (a, b):
                body = await c.expect(CsOp.OUT_CHANNEL_OUT)
                assert struct.unpack_from("<i", body, 0) == (bia.id,)

            # B volta ao lobby e cai sem sair: a queda da conexão gera a saída para A.
            await b.send(CsOp.IN_CHANNEL)
            await b.expect(CsOp.CHANNEL_PLAYER_INFO_OUT)
            await b.expect(CsOp.CHANNEL_ROOM_INFO_OUT)
            await b.expect(CsOp.IN_CHANNEL_OUT)
            await a.expect(CsOp.IN_CHANNEL_OUT)
            b.writer.close()
            body = await a.expect(CsOp.OUT_CHANNEL_OUT)
            assert struct.unpack_from("<i", body, 0) == (bia.id,)


async def test_pedidos_fora_de_ordem_e_opcodes_desconhecidos_nao_derrubam(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))

    async with channel_server(settings) as ch, _connect(ch, CHANNEL_NET_CODE) as c:
        await c.send(182, b"\x01\x02")  # opcode sem handler
        await c.send(CsOp.IN_CHANNEL)  # sem login: ignorado
        await c.send(CsOp.SEND_MESSAGE, bytes([0, 1]) + b"x")  # sem login: ignorado
        await c.send(CsOp.HEARTBEAT)  # cliente: sem resposta
        await c.assert_silencio()

        await c.send(CsOp.IN_CHANNEL_SERVER, _login_payload("f" * 32))
        body = await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
        assert struct.unpack_from("<i", body, 0xA8) == (-160,)
        await c.send(CsOp.IN_CHANNEL_SERVER, b"curto")  # payload inválido: ignorado
        await c.send(182, b"")
        await c.send(CsOp.IN_CHANNEL_SERVER, _login_payload(TOKEN_ANA))
        await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
        await c.expect(CsOp.CHANNEL_INFO_OUT)


async def test_servidor_envia_heartbeat_periodico() -> None:
    server = await start_service(
        "127.0.0.1",
        0,
        net_code=CHANNEL_NET_CODE,
        router={},
        recv_timeout=60,
        heartbeat=CsHeartbeat(),
        heartbeat_every=0.05,
    )
    async with server:
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        c = Client(reader, writer, CHANNEL_NET_CODE)
        try:
            assert await c.expect(CsOp.HEARTBEAT) == b""
            assert await c.expect(CsOp.HEARTBEAT) == b""
        finally:
            writer.close()
