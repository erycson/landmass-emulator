"""Composição: liga settings, banco, repositórios, handlers e servidores."""

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.engine import migrate
from landmass_emu.domain.channel import Channel
from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.session_keys import MemorySessionKeyRegistry
from landmass_emu.handlers.channel import build_router as build_channel_router
from landmass_emu.handlers.channel import disconnect_handler
from landmass_emu.handlers.message import build_router
from landmass_emu.net.server import start_service
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.session_keys import SessionKeyRegistry
from landmass_emu.protocol.channel import CsHeartbeat
from landmass_emu.protocol.header import CHANNEL_NET_CODE, MESSAGE_NET_CODE
from landmass_emu.settings import Settings

# Heartbeat do servidor no canal. `time_out` do [CHANNEL] no config.ini do cliente é 20000
# (unidade não confirmada); 10 s deixa margem para o cliente.
CHANNEL_HEARTBEAT_SECONDS = 10.0


def channels_from(settings: Settings) -> Sequence[Channel]:
    return [
        Channel(
            server_id=i,
            name=c.name,
            address=c.address or settings.public_host,
            port=c.port or settings.channel_port,
            max_clients=c.max_clients,
        )
        for i, c in enumerate(settings.channels, start=1)
    ]


@asynccontextmanager
async def open_accounts(settings: Settings) -> AsyncIterator[AccountRepository]:
    await migrate(settings.database_url)
    engine = create_async_engine(settings.database_url)
    try:
        yield SqlAccountRepository(async_sessionmaker(engine, expire_on_commit=False))
    finally:
        await engine.dispose()


@asynccontextmanager
async def _listening(server: asyncio.Server) -> AsyncIterator[asyncio.Server]:
    try:
        yield server
    finally:
        server.close()
        server.close_clients()
        await server.wait_closed()


@asynccontextmanager
async def message_server(
    settings: Settings, sessions: SessionKeyRegistry
) -> AsyncIterator[asyncio.Server]:
    async with open_accounts(settings) as accounts:
        server = await start_service(
            settings.bind_host,
            settings.message_port,
            net_code=MESSAGE_NET_CODE,
            router=build_router(accounts, channels_from(settings), sessions),
            recv_timeout=settings.recv_timeout,
        )
        async with _listening(server) as listening:
            yield listening


@asynccontextmanager
async def channel_server(
    settings: Settings, sessions: SessionKeyRegistry
) -> AsyncIterator[asyncio.Server]:
    lobby = Lobby()
    server = await start_service(
        settings.bind_host,
        settings.channel_port,
        net_code=CHANNEL_NET_CODE,
        router=build_channel_router(sessions, lobby),
        recv_timeout=settings.recv_timeout,
        on_close=disconnect_handler(lobby),
        heartbeat=CsHeartbeat(),
        heartbeat_every=CHANNEL_HEARTBEAT_SECONDS,
    )
    async with _listening(server) as listening:
        yield listening


@asynccontextmanager
async def game_servers(settings: Settings) -> AsyncIterator[tuple[asyncio.Server, asyncio.Server]]:
    """Message e Channel com o mesmo registro: a chave emitida no 111 vale no 100."""
    sessions = MemorySessionKeyRegistry()
    async with (
        message_server(settings, sessions) as message,
        channel_server(settings, sessions) as channel,
    ):
        yield message, channel
