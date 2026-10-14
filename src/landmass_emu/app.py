"""Composição: liga settings, banco, repositórios, handlers e servidores."""

import asyncio
import logging
import random
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from landmass_emu.audit import EconomyAudit
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.catalog import WdbCatalog
from landmass_emu.db.clans import SqlClanRepository
from landmass_emu.db.consumables import SqlConsumableRepository
from landmass_emu.db.engine import Migrator
from landmass_emu.db.equipment import SqlEquipmentRepository
from landmass_emu.db.gifts import SqlGiftRepository
from landmass_emu.db.inventory import SqlInventoryRepository
from landmass_emu.db.item_catalog import LazyItemCatalog
from landmass_emu.db.matches import SqlMatchRepository
from landmass_emu.db.options import SqlOptionsRepository
from landmass_emu.db.profile import SqlPlayerProfileRepository
from landmass_emu.db.progression import SqlProgressionRepository
from landmass_emu.db.ranking import SqlRankingRepository
from landmass_emu.db.shop import SqlShopItemRepository, SqlShopRepository
from landmass_emu.db.social import SqlSocialRepository
from landmass_emu.db.use import SqlUseRepository
from landmass_emu.domain.bots import BotLoadout
from landmass_emu.domain.channel import Channel
from landmass_emu.domain.consumables import ConsumableService
from landmass_emu.domain.equipment import EquipService
from landmass_emu.domain.gift import GiftService
from landmass_emu.domain.inventory import InventoryService
from landmass_emu.domain.lifecycle import DestroyService, ExtendService
from landmass_emu.domain.loadout import LoadoutService
from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.locks import AccountLocks
from landmass_emu.domain.presence import MessagePresence
from landmass_emu.domain.rooms import Rooms
from landmass_emu.domain.session_keys import MemorySessionKeyRegistry
from landmass_emu.domain.shop import ShopService
from landmass_emu.domain.use import ItemUseService
from landmass_emu.handlers.channel import ChannelHandlers
from landmass_emu.handlers.channel.equipment import EquipmentHandlers
from landmass_emu.handlers.channel.gift import GiftHandlers
from landmass_emu.handlers.channel.notice import GlobalNotice
from landmass_emu.handlers.message import MessageHandlers
from landmass_emu.hosting.fixed import FixedMatchHost
from landmass_emu.hosting.player_records import PlayerRecordFile
from landmass_emu.hosting.process import ProcessHostConfig, ProcessMatchHost
from landmass_emu.net.server import Service
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.clans import ClanRepository
from landmass_emu.ports.inventory import InventoryRepository
from landmass_emu.ports.match_host import GameEndpoint, MatchHost
from landmass_emu.ports.matches import MatchRepository
from landmass_emu.ports.options import OptionsRepository
from landmass_emu.ports.profile import PlayerProfileRepository
from landmass_emu.ports.progression import ProgressionRepository
from landmass_emu.ports.ranking import RankingRepository
from landmass_emu.ports.session_keys import SessionKeyRegistry
from landmass_emu.ports.shop import ShopItemRepository
from landmass_emu.ports.social import SocialRepository
from landmass_emu.protocol.channel import CsHeartbeat
from landmass_emu.protocol.header import CHANNEL_NET_CODE, MESSAGE_NET_CODE
from landmass_emu.settings import Settings
from landmass_emu.shutdown import Shutdown
from landmass_emu.update.ftp import FtpServer

log = logging.getLogger(__name__)

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
            mode=c.mode,
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
    *,
    accepting: Callable[[], bool] | None = None,
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
        accepting=accepting,
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
    equipment: EquipmentHandlers,
    audit: EconomyAudit,
    profiles: PlayerProfileRepository,
    gifts: GiftService,
    loadout: LoadoutService,
    shutdown: Shutdown,
) -> AsyncIterator[asyncio.Server]:
    lobby = Lobby()
    rooms = Rooms(solo=settings.match_bots > 0)
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
        equipment=equipment,
        audit=audit,
        profiles=profiles,
        gifts=GiftHandlers(gifts, lobby, audit),
        loadout=loadout,
        accepting_matches=shutdown.accepting,
        match_bots=settings.match_bots,
    )
    shutdown.attach(_ChannelShutdown(GlobalNotice(lobby), lobby, handlers))
    server = await Service(
        net_code=CHANNEL_NET_CODE,
        router=handlers.router,
        recv_timeout=settings.recv_timeout,
        on_close=handlers.disconnect,
        heartbeat=CsHeartbeat(),
        heartbeat_every=CHANNEL_HEARTBEAT_SECONDS,
        accepting=shutdown.accepting,
    ).start(settings.bind_host, settings.channel_port)
    try:
        async with _listening(server) as listening:
            yield listening
    finally:
        await match.close()


class _ChannelShutdown:
    """Ponte do desligamento para o canal: aviso ao lobby, contagem de quem está nele e partidas."""

    def __init__(self, notice: GlobalNotice, lobby: Lobby, handlers: ChannelHandlers) -> None:
        self._notice = notice
        self._lobby = lobby
        self._handlers = handlers

    def notify(self, text: str) -> None:
        self._notice.send(text)

    def players(self) -> int:
        return self._lobby.size()

    async def end_matches(self) -> None:
        await self._handlers.end_matches()


async def warn_empty_shop(items: ShopItemRepository) -> None:
    """Sem linha em `shop_items`, nada está à venda (D191). Só avisa: o servidor sobe mesmo."""
    if await items.count() == 0:
        log.warning("loja vazia: nada à venda; rode 'landmass-emu shop sync' com o cliente")


@asynccontextmanager
async def update_server(settings: Settings) -> AsyncIterator[asyncio.Server | None]:
    """FTP de atualização (D241), só com `update_port`. Sem a porta, não sobe e não cria pasta."""
    if settings.update_port is None:
        yield None
        return
    settings.update_dir.mkdir(parents=True, exist_ok=True)
    ftp = FtpServer(settings.update_dir, settings.update_user, settings.update_password)
    server = await ftp.start(settings.bind_host, settings.update_port)
    async with _listening(server) as listening:
        yield listening


@asynccontextmanager
async def game_servers(
    settings: Settings, shutdown: Shutdown | None = None
) -> AsyncIterator[tuple[asyncio.Server, asyncio.Server]]:
    """Message e Channel com o mesmo registro de sessão e o mesmo banco: a chave emitida no 111
    vale no 100, e as opções gravadas no 544 voltam no 111 do próximo login. `shutdown` é o estado
    do desligamento; sem ele, o servidor roda até ser cancelado, como antes do D202."""
    if shutdown is None:
        shutdown = Shutdown(settings.shutdown_notice_seconds)
    sessions = MemorySessionKeyRegistry()
    async with open_database(settings) as db:
        await warn_empty_shop(SqlShopItemRepository(db))
        accounts = SqlAccountRepository(db)
        options = SqlOptionsRepository(db)
        progression = SqlProgressionRepository(db)
        inventory = SqlInventoryRepository(db)
        social = SqlSocialRepository(db)
        clans = SqlClanRepository(db)
        ranking = SqlRankingRepository(db)
        profiles = SqlPlayerProfileRepository(db)
        shop, equipment, audit, gifts, loadout = _game_services(
            settings, db, accounts, progression, inventory
        )
        matches = SqlMatchRepository(db)
        async with (
            message_server(
                settings,
                sessions,
                accounts,
                options,
                social,
                clans,
                ranking,
                accepting=shutdown.accepting,
            ) as message,
            channel_server(
                settings,
                sessions,
                options,
                progression,
                accounts,
                inventory,
                shop,
                matches,
                equipment,
                audit,
                profiles,
                gifts,
                loadout,
                shutdown,
            ) as channel,
        ):
            yield message, channel


def _game_services(
    settings: Settings,
    db: async_sessionmaker[AsyncSession],
    accounts: AccountRepository,
    progression: ProgressionRepository,
    inventory: InventoryRepository,
) -> tuple[ShopService, EquipmentHandlers, EconomyAudit, GiftService, LoadoutService]:
    """Compra e F6/F7 com o mesmo catálogo (LazyItemCatalog, o canal sobe sem o wdb) e a mesma trava
    por conta: uma conta não compra e equipa ao mesmo tempo. O equipamento da partida (D190) lê o
    mesmo catálogo."""
    wdb = settings.client_dir / "landmass.wdb"
    catalog = LazyItemCatalog(wdb)
    levels = WdbCatalog(wdb)
    locks = AccountLocks()
    equipment = SqlEquipmentRepository(db)
    audit = EconomyAudit.open(settings.audit_log, catalog)
    shop = ShopService(
        catalog=catalog,
        items=SqlShopItemRepository(db),
        levels=levels,
        inventory=InventoryService(catalog),
        repository=inventory,
        accounts=accounts,
        progression=progression,
        purchases=SqlShopRepository(db),
        locks=locks,
    )
    inventory_service = InventoryService(catalog)
    use = ItemUseService(
        names=catalog,
        inventory=inventory_service,
        items=inventory,
        accounts=accounts,
        progression=progression,
        repository=SqlUseRepository(db),
        locks=locks,
    )
    gifts = GiftService(
        catalog=catalog,
        inventory=inventory_service,
        items=inventory,
        accounts=accounts,
        progression=progression,
        repository=SqlGiftRepository(db),
        locks=locks,
    )
    # Bots (D220, D221) só com a pasta do servidor de partida: o LMEmu.ini e o MORATS.upl são dela.
    bots = None
    if settings.match_bots and settings.match_server_dir is not None:
        records = PlayerRecordFile(settings.match_server_dir / "MORATS.upl")
        bots = BotLoadout(catalog=catalog, records=records, rng=random.Random())
    loadout = LoadoutService(catalog=catalog, inventory=inventory, accounts=accounts, bots=bots)
    handlers = EquipmentHandlers(
        equip=EquipService(
            catalog=catalog,
            levels=levels,
            inventory=inventory,
            equipment=equipment,
            accounts=accounts,
            progression=progression,
            locks=locks,
        ),
        destroy=DestroyService(inventory=inventory, equipment=equipment, locks=locks),
        consumables=ConsumableService(
            inventory=inventory,
            repository=SqlConsumableRepository(db),
            locks=locks,
        ),
        extend=ExtendService(
            catalog=catalog,
            inventory=inventory,
            equipment=equipment,
            progression=progression,
            locks=locks,
        ),
        audit=audit,
        use=use,
    )
    return shop, handlers, audit, gifts, loadout
