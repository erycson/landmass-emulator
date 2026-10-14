"""Inventário no Channel Server (handlers reais sobre SQLite de tmp_path), admins e CLI."""

import argparse
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.__main__ import _parser
from landmass_emu.admin_inventory import InventoryAdmin, StarterKitAdmin
from landmass_emu.app import open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.inventory import SqlInventoryRepository
from landmass_emu.db.progression import SqlProgressionRepository
from landmass_emu.domain.account import Account, hash_token
from landmass_emu.domain.inventory import ApplyFlag, InventoryService, ItemUnit, MoratUnit
from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.match import MapRecord
from landmass_emu.domain.rooms import Rooms
from landmass_emu.domain.session_keys import MemorySessionKeyRegistry
from landmass_emu.domain.starter_kit import STARTER_MORATS, StarterKit
from landmass_emu.handlers.channel import ChannelHandlers
from landmass_emu.hosting.fixed import FixedMatchHost
from landmass_emu.net.session import Session
from landmass_emu.ports.match_host import GameEndpoint
from landmass_emu.protocol.channel import CsInChannelServerIn, CsInChannelServerOut, CsOp
from landmass_emu.protocol.inventory import (
    CsGetItemOut,
    CsGetMoratsOut,
    CsInventoryOp,
    CsSetRegularOut,
)
from landmass_emu.protocol.progression import CsProgressionOp
from landmass_emu.settings import Settings

TOKEN_ANA = "0123456789abcdef0123456789abcdef"
TOKEN_BIA = "fedcba9876543210fedcba9876543210"
AGORA = datetime(2026, 1, 1, tzinfo=UTC)
PRAZO = datetime(2026, 1, 4, tzinfo=UTC)  # 1767484800 em segundos Unix
ITEM = 1
ITEM_EQUIP = 2
MORAT = 101000001


class FakeCatalog:
    def __init__(self, itens: frozenset[int], morats: frozenset[int]) -> None:
        self._itens = itens
        self._morats = morats

    def is_inventory_item(self, catalog_id: int) -> bool:
        return catalog_id in self._itens

    def is_morat(self, catalog_id: int) -> bool:
        return catalog_id in self._morats


def _guids() -> Callable[[], str]:
    contador = iter(range(1, 1_000_000))
    return lambda: str(uuid.UUID(int=next(contador)))


def _servico() -> InventoryService:
    catalogo = FakeCatalog(frozenset({ITEM, ITEM_EQUIP}), frozenset(STARTER_MORATS))
    return InventoryService(catalogo, clock=lambda: AGORA, new_guid=_guids())


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
        client_dir=tmp_path,
    )


def _sync_engine(tmp_path: Path) -> Engine:
    return create_engine(f"sqlite:///{tmp_path.as_posix()}/landmass.db")


def _guid(n: int) -> str:
    return f"{n:036d}"  # 36 caracteres


def _payload_chave(chave: str) -> bytes:
    """CS_IN_CHANNEL_SERVER_IN: `char[33]` com NUL. O dataclass só tem `unpack`."""
    return chave.encode("ascii").ljust(33, b"\0")


def _regular(tmp_path: Path, conta_id: int) -> tuple[int | None, int | None]:
    engine = _sync_engine(tmp_path)
    try:
        with engine.connect() as conn:
            linha = conn.execute(
                text("SELECT regular_nest_id, regular_morat_class FROM accounts WHERE id = :id"),
                {"id": conta_id},
            ).one()
    finally:
        engine.dispose()
    return linha[0], linha[1]


def _morat(conta_id: int, indice: int, gate: int, guid: str, catalogo: int) -> MoratUnit:
    return MoratUnit(
        account_id=conta_id,
        inventory_index=indice,
        catalog_id=catalogo,
        item_guid=guid,
        gate_index=gate,
        apply_flag=ApplyFlag.UNLIMIT,
        apply_value=None,
        expires_at=None,
    )


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with open_database(_settings(tmp_path)) as sessoes:
        yield sessoes


async def _conta(db: async_sessionmaker[AsyncSession], usuario: str, token: str) -> Account:
    return await SqlAccountRepository(db).create(usuario, usuario.title(), hash_token(token))


class _Mapas:
    """Catálogo de teste: todo mapa existe (o canal só o consulta ao iniciar partida)."""

    def get(self, record_id: int) -> MapRecord | None:
        return MapRecord(record_id=record_id, file_name="ONS-Treino", player_max=32, op_type=0)


def _canal(
    db: async_sessionmaker[AsyncSession], sessoes: MemorySessionKeyRegistry
) -> ChannelHandlers:
    return ChannelHandlers(
        sessoes,
        Lobby(),
        Rooms(),
        None,
        SqlProgressionRepository(db),
        FixedMatchHost(GameEndpoint("127.0.0.1", 7777)),
        _Mapas(),
        None,
        SqlAccountRepository(db),
        SqlInventoryRepository(db),
        None,
    )


async def test_login_manda_101_com_nest_e_gates_depois_102_e_103(
    db: async_sessionmaker[AsyncSession],
) -> None:
    ana = await _conta(db, "ana", TOKEN_ANA)
    await SqlAccountRepository(db).set_regular(ana.id, 2, 3)
    inv = SqlInventoryRepository(db)
    await inv.add_item(
        ItemUnit(
            account_id=ana.id,
            inventory_index=1,
            catalog_id=ITEM,
            item_guid=_guid(1),
            apply_flag=ApplyFlag.REALTIME,
            apply_value=None,
            expires_at=PRAZO,
        )
    )
    # Gravados fora de ordem: a leitura devolve por índice, então o gate 0 vem primeiro.
    await inv.add_morat(_morat(ana.id, 2, 2, _guid(2), 103000001))
    await inv.add_morat(_morat(ana.id, 0, 0, _guid(3), 101000001))

    sessoes = MemorySessionKeyRegistry()
    canal = _canal(db, sessoes)
    chave = sessoes.issue(ana)
    payload = _payload_chave(chave)
    assert CsInChannelServerIn.unpack(payload) == CsInChannelServerIn(chave)

    replies = await canal.router[CsOp.IN_CHANNEL_SERVER](Session(peer="t"), payload)

    assert [r.opcode for r in replies] == [
        CsOp.IN_CHANNEL_SERVER_OUT,
        CsOp.CHANNEL_INFO_OUT,
        CsProgressionOp.CHARGE_CASH_OUT,
        CsProgressionOp.CHARGE_POINT_OUT,
        CsInventoryOp.GET_ITEM_OUT,
        CsInventoryOp.GET_MORATS_OUT,
        CsInventoryOp.GET_MORATS_OUT,
    ]
    login = replies[0]
    assert isinstance(login, CsInChannelServerOut)
    assert (login.client_guid, login.result) == (ana.id, 0)
    assert (login.progress.nest, login.progress.morat_gates) == (2, (0, 2))
    item = replies[4]
    assert isinstance(item, CsGetItemOut)
    assert (item.inventory_index, item.catalog_id, item.apply_flag) == (1, ITEM, 2)
    assert item.apply_value == 1767484800
    morat_0, morat_2 = replies[5], replies[6]
    assert isinstance(morat_0, CsGetMoratsOut) and morat_0.gate_index == 0
    assert isinstance(morat_2, CsGetMoratsOut) and morat_2.gate_index == 2


async def test_conta_sem_inventario_recebe_so_101_e_111(
    db: async_sessionmaker[AsyncSession],
) -> None:
    bia = await _conta(db, "bia", TOKEN_BIA)
    sessoes = MemorySessionKeyRegistry()
    canal = _canal(db, sessoes)

    replies = await canal.router[CsOp.IN_CHANNEL_SERVER](
        Session(peer="t"), _payload_chave(sessoes.issue(bia))
    )

    # Sem inventário: nenhum 102 nem 103, só 101, 111 e os pushes de saldo da F3.
    assert [r.opcode for r in replies] == [
        CsOp.IN_CHANNEL_SERVER_OUT,
        CsOp.CHANNEL_INFO_OUT,
        CsProgressionOp.CHARGE_CASH_OUT,
        CsProgressionOp.CHARGE_POINT_OUT,
    ]
    login = replies[0]
    assert isinstance(login, CsInChannelServerOut)
    assert (login.progress.nest, login.progress.morat_gates) == (0, ())


async def test_chave_recusada_nao_lista_inventario(db: async_sessionmaker[AsyncSession]) -> None:
    ana = await _conta(db, "ana", TOKEN_ANA)
    await SqlInventoryRepository(db).add_morat(_morat(ana.id, 0, 0, _guid(1), 101000001))
    canal = _canal(db, MemorySessionKeyRegistry())

    replies = await canal.router[CsOp.IN_CHANNEL_SERVER](
        Session(peer="t"), _payload_chave("f" * 32)
    )

    assert [r.opcode for r in replies] == [CsOp.IN_CHANNEL_SERVER_OUT]
    assert isinstance(replies[0], CsInChannelServerOut)
    assert replies[0].result == -160


async def test_set_regular_sem_login_nao_responde_nem_grava(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    ana = await _conta(db, "ana", TOKEN_ANA)
    canal = _canal(db, MemorySessionKeyRegistry())

    replies = await canal.router[CsInventoryOp.SET_REGULAR_IN](Session(peer="t"), bytes([2, 3]))

    assert replies == []
    assert _regular(tmp_path, ana.id) == (None, None)


async def test_set_regular_com_login_grava_nest_e_classe(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    ana = await _conta(db, "ana", TOKEN_ANA)
    canal = _canal(db, MemorySessionKeyRegistry())

    replies = await canal.router[CsInventoryOp.SET_REGULAR_IN](
        Session(peer="t", account=ana), bytes([2, 3])
    )

    assert len(replies) == 1
    assert isinstance(replies[0], CsSetRegularOut)
    assert _regular(tmp_path, ana.id) == (2, 3)


@pytest.mark.parametrize("payload", [bytes([0, 1]), bytes([4, 1]), bytes([2, 0]), bytes([2, 5])])
async def test_set_regular_fora_da_faixa_levanta_e_nao_grava(
    db: async_sessionmaker[AsyncSession], tmp_path: Path, payload: bytes
) -> None:
    ana = await _conta(db, "ana", TOKEN_ANA)
    canal = _canal(db, MemorySessionKeyRegistry())

    with pytest.raises(ValueError):
        await canal.router[CsInventoryOp.SET_REGULAR_IN](Session(peer="t", account=ana), payload)

    assert _regular(tmp_path, ana.id) == (None, None)


async def test_kit_cria_quatro_morats_e_e_idempotente(
    db: async_sessionmaker[AsyncSession],
) -> None:
    ana = await _conta(db, "ana", TOKEN_ANA)
    inv = SqlInventoryRepository(db)
    admin = StarterKitAdmin(SqlAccountRepository(db), inv, StarterKit(_servico()))

    assert await admin.apply("ana") == 4
    morats = await inv.morats(ana.id)
    assert [(m.gate_index, m.catalog_id) for m in morats] == [
        (0, 101000001),
        (1, 102000001),
        (2, 103000001),
        (3, 104000001),
    ]

    assert await admin.apply("ana") == 0
    assert len(await inv.morats(ana.id)) == 4


async def test_kit_aplicado_vai_no_login_com_gates_habilitados(
    db: async_sessionmaker[AsyncSession],
) -> None:
    # Gate sem morat não basta: o cliente trava na sala sem nenhum gate habilitado.
    ana = await _conta(db, "ana", TOKEN_ANA)
    await StarterKitAdmin(
        SqlAccountRepository(db), SqlInventoryRepository(db), StarterKit(_servico())
    ).apply("ana")
    sessoes = MemorySessionKeyRegistry()
    canal = _canal(db, sessoes)

    replies = await canal.router[CsOp.IN_CHANNEL_SERVER](
        Session(peer="t"), _payload_chave(sessoes.issue(ana))
    )

    login = replies[0]
    assert isinstance(login, CsInChannelServerOut)
    assert login.progress.morat_gates == (0, 1, 2, 3)
    corpo = login.pack()
    assert [corpo[0x5C + 4 * g] for g in range(8)] == [1, 1, 1, 1, 0, 0, 0, 0]
    morats = [r for r in replies if isinstance(r, CsGetMoratsOut)]
    assert [(m.gate_index, m.catalog_id) for m in morats] == [
        (0, 101000001),
        (1, 102000001),
        (2, 103000001),
        (3, 104000001),
    ]


async def test_kit_conta_inexistente_levanta(db: async_sessionmaker[AsyncSession]) -> None:
    admin = StarterKitAdmin(
        SqlAccountRepository(db),
        SqlInventoryRepository(db),
        StarterKit(_servico()),
    )
    with pytest.raises(ValueError, match="não existe"):
        await admin.apply("fantasma")


def _admin(db: async_sessionmaker[AsyncSession]) -> InventoryAdmin:
    return InventoryAdmin(SqlAccountRepository(db), SqlInventoryRepository(db), _servico())


async def test_admin_morat_em_gate_9_levanta_e_nao_grava(
    db: async_sessionmaker[AsyncSession],
) -> None:
    ana = await _conta(db, "ana", TOKEN_ANA)
    with pytest.raises(ValueError, match="gate"):
        await _admin(db).add_morat("ana", MORAT, 9)
    assert await SqlInventoryRepository(db).morats(ana.id) == []


async def test_admin_item_com_catalogo_de_morat_levanta_e_nao_grava(
    db: async_sessionmaker[AsyncSession],
) -> None:
    ana = await _conta(db, "ana", TOKEN_ANA)
    with pytest.raises(ValueError, match="não é item"):
        await _admin(db).add_item("ana", MORAT, 3)
    assert await SqlInventoryRepository(db).items(ana.id) == []


async def test_admin_grava_item_e_morat(db: async_sessionmaker[AsyncSession]) -> None:
    ana = await _conta(db, "ana", TOKEN_ANA)
    admin = _admin(db)
    item = await admin.add_item("ana", ITEM, 3)
    morat = await admin.add_morat("ana", MORAT, 0)
    inv = SqlInventoryRepository(db)
    assert await inv.items(ana.id) == [item]
    assert await inv.morats(ana.id) == [morat]


async def test_admin_conta_inexistente_levanta(db: async_sessionmaker[AsyncSession]) -> None:
    with pytest.raises(ValueError, match="não existe"):
        await _admin(db).add_item("fantasma", ITEM, 3)


def _cli(linha: str) -> argparse.Namespace:
    """Faz o parse sem executar: `_parser()` não roda o comando."""
    return _parser().parse_args(linha.split())


def test_cli_account_token() -> None:
    args = _cli("account token --user x")
    assert args.action == "token"
    assert args.user == "x"


def test_cli_item_add() -> None:
    args = _cli("account item add bob --catalog 1 --days 3")
    assert (args.action, args.op) == ("item", "add")
    assert (args.username, args.catalog, args.days) == ("bob", 1, 3)


def test_cli_morat_add() -> None:
    args = _cli("account morat add bob --catalog 101000001 --gate 0")
    assert (args.action, args.op) == ("morat", "add")
    assert (args.username, args.catalog, args.gate) == ("bob", 101000001, 0)


def test_cli_kit_apply() -> None:
    args = _cli("account kit apply teste")
    assert (args.action, args.op) == ("kit", "apply")
    assert args.username == "teste"


def test_cli_account_create() -> None:
    args = _cli("account create --user a --nickname b")
    assert args.action == "create"
    assert (args.user, args.nickname) == ("a", "b")
