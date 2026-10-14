import asyncio
import contextlib
import re
import struct
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from landmass_emu.app import message_server, open_accounts, open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.clans import SqlClanRepository
from landmass_emu.db.options import SqlOptionsRepository
from landmass_emu.db.ranking import SqlRankingRepository
from landmass_emu.db.social import SqlSocialRepository
from landmass_emu.domain.account import hash_token
from landmass_emu.domain.session_keys import MemorySessionKeyRegistry
from landmass_emu.net.framing import encode_frame, read_frame
from landmass_emu.net.server import Service
from landmass_emu.protocol.header import MESSAGE_NET_CODE, pack_header, unpack_header
from landmass_emu.protocol.message import (
    MsAccountIdIn,
    MsLoginIn,
    MsNickIn,
    MsOp,
    MsRelationIdsIn,
    MsSendWhisperIn,
)
from landmass_emu.settings import Settings

TOKEN = "0123456789abcdef0123456789abcdef"
TOKEN_BIA = "fedcba9876543210fedcba9876543210"


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


@asynccontextmanager
async def _servidor(
    settings: Settings, registro: MemorySessionKeyRegistry
) -> AsyncIterator[asyncio.Server]:
    async with (
        open_database(settings) as db,
        message_server(
            settings,
            registro,
            SqlAccountRepository(db),
            SqlOptionsRepository(db),
            SqlSocialRepository(db),
            SqlClanRepository(db),
            SqlRankingRepository(db),
        ) as server,
    ):
        yield server


async def test_sequencia_de_login_ate_lista_de_canais(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        await accounts.create("fulano", "Fulano", hash_token(TOKEN))

    registro = MemorySessionKeyRegistry()
    async with _servidor(settings, registro) as server, _connect(server) as c:
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
        _servidor(settings, MemorySessionKeyRegistry()) as server,
        _connect(server) as c,
    ):
        await c.send(MsOp.GET_CHANNEL_SERVER_INFO)
        await c.send(1, b"\x01\x02")  # opcode 1 não tem handler no Message
        await c.send(MsOp.HEARTBEAT)
        await c.send(MsOp.LOGIN, b"\x01")  # payload curto: ignorado
        await c.send(MsOp.LOGIN, MsLoginIn(login_num=TOKEN).pack())
        op, body = await c.recv()
        assert op == MsOp.LOGIN_OUT and struct.unpack_from("<i", body, 4) == (0,)

        await c.send(1, b"\x01\x02")
        await c.send(MsOp.GET_CHANNEL_SERVER_INFO)
        op, _ = await c.recv()
        assert op == MsOp.GET_CHANNEL_SERVER_OUT


async def test_token_invalido_mantem_conexao_sem_login(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        await accounts.create("fulano", "Fulano", hash_token(TOKEN))

    async with (
        _servidor(settings, MemorySessionKeyRegistry()) as server,
        _connect(server) as c,
    ):
        await c.send(MsOp.LOGIN, MsLoginIn(login_num="f" * 32).pack())
        op, body = await c.recv()
        assert op == MsOp.LOGIN_OUT and struct.unpack_from("<i", body, 4) == (-160,)
        await c.send(MsOp.GET_CHANNEL_SERVER_INFO)
        await c.assert_silencio()


async def test_sem_trafego_desconecta(tmp_path: Path) -> None:
    server = await Service(net_code=MESSAGE_NET_CODE, router={}, recv_timeout=0.2).start(
        "127.0.0.1", 0
    )
    port = server.sockets[0].getsockname()[1]
    async with server:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        async with asyncio.timeout(5):
            assert await reader.read() == b""
        writer.close()


async def _logar(c: Client, token: str) -> None:
    await c.send(MsOp.LOGIN, MsLoginIn(login_num=token).pack())
    op, body = await c.recv()
    assert op == MsOp.LOGIN_OUT and struct.unpack_from("<i", body, 4) == (0,)


async def test_amizade_sussurro_e_queda_entre_duas_contas(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        bia_id = (await accounts.create("bia", "Bia", hash_token(TOKEN_BIA))).id
        await accounts.create("ana", "Ana", hash_token(TOKEN))

    async with (
        _servidor(settings, MemorySessionKeyRegistry()) as server,
        _connect(server) as ana,
        _connect(server) as bia,
    ):
        await _logar(ana, TOKEN)
        await _logar(bia, TOKEN_BIA)

        # Amizade com Bia conectada: 183 com o id, o nick e o estado 0x22 (conectado).
        await ana.send(MsOp.ADD_FRIEND, MsNickIn("Bia").pack())
        op, body = await ana.recv()
        assert op == MsOp.FRIEND_LIST_OUT
        assert struct.unpack_from("<i", body, 0) == (bia_id,)
        assert body[4:0x14].split(b"\0", 1)[0] == b"Bia"
        assert body[0x25] == 0x22

        # Sussurro: 161 vai só à Bia, com o remetente em @0 e o texto em @0x14.
        await ana.send(MsOp.SEND_WHISPER, MsSendWhisperIn("Bia", b"oi!").pack())
        op, body = await bia.recv()
        assert op == MsOp.SEND_WHISPER_OUT
        assert body[:18].split(b"\0", 1)[0] == b"Ana"
        assert body[0x14:] == b"oi!"
        await ana.assert_silencio()

        # Bia cai: a presença sai no fechamento da conexão. A consulta 190 mostra o estado 0.
        bia.writer.close()
        for _ in range(50):
            await ana.send(MsOp.REFRESH_FRIEND, MsRelationIdsIn((bia_id,)).pack())
            op, body = await ana.recv()
            assert op == MsOp.REFRESH_FRIEND_OUT
            if body[4 + 0x11] == 0:
                break
            await asyncio.sleep(0.02)
        else:
            raise AssertionError("Bia continuou online depois da queda")

        await ana.send(MsOp.SEND_WHISPER, MsSendWhisperIn("Bia", b"oi?").pack())
        op, body = await ana.recv()
        assert op == MsOp.SEND_WHISPER_ERROR_OUT
        assert struct.unpack_from("<i", body, 0) == (-19,)

    # Reinício do servidor: a amizade continua no banco e volta no 183 do próximo login.
    async with (
        _servidor(settings, MemorySessionKeyRegistry()) as server,
        _connect(server) as ana,
    ):
        await _logar(ana, TOKEN)
        await ana.send(MsOp.GET_FRIEND_LIST)
        op, body = await ana.recv()
        assert op == MsOp.FRIEND_LIST_OUT
        assert struct.unpack_from("<i", body, 0) == (bia_id,)

        await ana.send(MsOp.DEL_FRIEND, MsAccountIdIn(bia_id).pack())
        op, body = await ana.recv()
        assert op == MsOp.DEL_FRIEND_OUT
        assert struct.unpack_from("<ii", body, 0) == (bia_id, 0)

        await ana.send(MsOp.GET_FRIEND_LIST)
        await ana.assert_silencio()  # lista vazia: nenhum pacote
