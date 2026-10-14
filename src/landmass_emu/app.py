"""Composição: liga settings, banco, repositórios, handlers e servidores."""

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.catalog import WdbCatalog
from landmass_emu.db.clans import SqlClanRepository
from landmass_emu.db.engine import Migrator
from landmass_emu.db.inventory import SqlInventoryRepository
from landmass_emu.db.item_catalog import LazyItemCatalog
from landmass_emu.db.matches import SqlMatchRepository
from landmass_emu.db.options import SqlOptionsRepository
from landmass_emu.db.progression import SqlProgressionRepository
from landmass_emu.db.ranking import SqlRankingRepository
from landmass_emu.db.shop import SqlShopRepository
from landmass_emu.db.social import SqlSocialRepository
from landmass_emu.domain.channel import Channel
from landmass_emu.domain.inventory import InventoryService
from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.presence import MessagePresence
from landmass_emu.domain.rooms import Rooms
from landmass_emu.domain.session_keys import MemorySessionKeyRegistry
from landmass_emu.domain.shop import ShopService
from landmass_emu.handlers.channel import ChannelHandlers
from landmass_emu.handlers.message import MessageHandlers
from landmass_emu.hosting.fixed import FixedMatchHost
from landmass_emu.hosting.process import ProcessHostConfig, ProcessMatchHost
from landmass_emu.net.server import Service
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.clans import ClanRepository
from landmass_emu.ports.inventory import InventoryRepository
from landmass_emu.ports.match_host import GameEndpoint, MatchHost
from landmass_emu.ports.matches import MatchRepository
from landmass_emu.ports.options import OptionsRepository
from landmass_emu.ports.progression import ProgressionRepository
from landmass_emu.ports.ranking import RankingRepository
from landmass_emu.ports.session_keys import SessionKeyRegistry
from landmass_emu.ports.social import SocialRepository
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
async def open_database(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    await Migrator(settings.database_url).upgrade()
    engine = create_async_engine(settings.database_url)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@asynccontextmanager
async def open_accounts(settings: Settings) -> AsyncIterator[AccountRepository]:
    async with open_database(settings) as db:
        yield SqlAccountRepository(db)


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
    settings: Settings,
    sessions: SessionKeyRegistry,
    accounts: AccountRepository,
    options: OptionsRepository,
    social: SocialRepository,
    clans: ClanRepository,
    ranking: RankingRepository,
) -> AsyncIterator[asyncio.Server]:
    presence = MessagePresence()
    handlers = MessageHandlers(
        accounts,
        channels_from(settings),
        sessions,
        options,
        social,
        presence,
        clans,
        ranking,
    )
    server = await Service(
        net_code=MESSAGE_NET_CODE,
        router=handlers.router,
        recv_timeout=settings.recv_timeout,
        on_close=presence.unbind,
    ).start(settings.bind_host, settings.message_port)
    async with _listening(server) as listening:
        yield listening


def match_host_from(settings: Settings) -> MatchHost:
    """Sem `LANDMASS_MATCH_SERVER_DIR`, a partida é o endereço fixo (`LANDMASS_GAME_HOST/PORT`).
    Com a pasta, cada sala em partida sobe o próprio servidor (docs/architecture/06)."""
    if settings.match_server_dir is None:
        return FixedMatchHost(GameEndpoint(settings.game_host, settings.game_port))
    return ProcessMatchHost(
        ProcessHostConfig(
            server_dir=settings.match_server_dir,
            game_host=settings.game_host,
            port_min=settings.match_port_min,
            port_max=settings.match_port_max,
            ready_timeout=settings.match_ready_timeout,
            message_addr=f"{settings.public_host}:{settings.message_port}",
            version=settings.client_version,
            login_num=settings.match_login_num or "",
        )
    )


@asynccontextmanager
async def channel_server(
    settings: Settings,
    sessions: SessionKeyRegistry,
    options: OptionsRepository,
    progression: ProgressionRepository,
    accounts: AccountRepository,
    inventory: InventoryRepository,
    shop: ShopService,
    matches: MatchRepository,
) -> AsyncIterator[asyncio.Server]:
    lobby = Lobby()
    rooms = Rooms()
    match = match_host_from(settings)
    maps = WdbCatalog(settings.client_dir / "landmass.wdb")
    handlers = ChannelHandlers(
        sessions,
        lobby,
        rooms,
        options,
        progression,
        match,
        maps,
        matches,
        accounts,
        inventory,
        shop,
    )
    server = await Service(
        net_code=CHANNEL_NET_CODE,
        router=handlers.router,
        recv_timeout=settings.recv_timeout,
        on_close=handlers.disconnect,
        heartbeat=CsHeartbeat(),
        heartbeat_every=CHANNEL_HEARTBEAT_SECONDS,
    ).start(settings.bind_host, settings.channel_port)
    try:
        async with _listening(server) as listening:
            yield listening
    finally:
        await match.close()


@asynccontextmanager
async def game_servers(settings: Settings) -> AsyncIterator[tuple[asyncio.Server, asyncio.Server]]:
    """Message e Channel com o mesmo registro de sessão e o mesmo banco: a chave emitida no 111
    vale no 100, e as opções gravadas no 544 voltam no 111 do próximo login."""
    sessions = MemorySessionKeyRegistry()
    async with open_database(settings) as db:
        accounts = SqlAccountRepository(db)
        options = SqlOptionsRepository(db)
        progression = SqlProgressionRepository(db)
        inventory = SqlInventoryRepository(db)
        social = SqlSocialRepository(db)
        clans = SqlClanRepository(db)
        ranking = SqlRankingRepository(db)
        shop = _shop_service(settings, accounts, progression, inventory, SqlShopRepository(db))
        matches = SqlMatchRepository(db)
        async with (
            message_server(
                settings, sessions, accounts, options, social, clans, ranking
            ) as message,
            channel_server(
                settings, sessions, options, progression, accounts, inventory, shop, matches
            ) as channel,
        ):
            yield message, channel


def _shop_service(
    settings: Settings,
    accounts: AccountRepository,
    progression: ProgressionRepository,
    inventory: InventoryRepository,
    purchases: SqlShopRepository,
) -> ShopService:
    """Catálogo lido na primeira compra (LazyItemCatalog): o canal sobe sem o wdb."""
    wdb = settings.client_dir / "landmass.wdb"
    catalog = LazyItemCatalog(wdb)
    return ShopService(
        catalog=catalog,
        levels=WdbCatalog(wdb),
        inventory=InventoryService(catalog),
        repository=inventory,
        accounts=accounts,
        progression=progression,
        purchases=purchases,
    )
