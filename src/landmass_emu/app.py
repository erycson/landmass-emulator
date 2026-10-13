"""Composição: liga settings, banco, repositórios, handlers e servidores."""

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.engine import migrate
from landmass_emu.domain.channel import Channel
from landmass_emu.handlers.message import build_router
from landmass_emu.net.server import start_service
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.protocol.header import MESSAGE_NET_CODE
from landmass_emu.settings import Settings


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
async def message_server(settings: Settings) -> AsyncIterator[asyncio.Server]:
    async with open_accounts(settings) as accounts:
        server = await start_service(
            settings.bind_host,
            settings.message_port,
            net_code=MESSAGE_NET_CODE,
            router=build_router(accounts, channels_from(settings)),
            recv_timeout=settings.recv_timeout,
        )
        try:
            yield server
        finally:
            server.close()
            server.close_clients()
            await server.wait_closed()
