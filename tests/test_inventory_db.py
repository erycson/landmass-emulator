"""Banco real do inventário (SQLite via `open_database`): esquema, repositórios e conflitos."""

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.app import open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.inventory import SqlInventoryRepository
from landmass_emu.domain.account import Account, hash_token
from landmass_emu.domain.inventory import ApplyFlag, ItemUnit, MoratUnit
from landmass_emu.ports.inventory import InventoryConflict
from landmass_emu.settings import Settings

TOKEN_ANA = "0123456789abcdef0123456789abcdef"
TOKEN_BIA = "fedcba9876543210fedcba9876543210"
PRAZO = datetime(2026, 1, 4, tzinfo=UTC)


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


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with open_database(_settings(tmp_path)) as sessoes:
        yield sessoes


async def _conta(db: async_sessionmaker[AsyncSession], usuario: str, token: str) -> Account:
    return await SqlAccountRepository(db).create(usuario, usuario.title(), hash_token(token))


def _item(conta_id: int, indice: int, guid: str, expires_at: datetime | None = PRAZO) -> ItemUnit:
    return ItemUnit(
        account_id=conta_id,
        inventory_index=indice,
        catalog_id=1,
        item_guid=guid,
        apply_flag=ApplyFlag.REALTIME,
        apply_value=None,
        expires_at=expires_at,
    )


def _morat(conta_id: int, indice: int, gate: int, guid: str) -> MoratUnit:
    return MoratUnit(
        account_id=conta_id,
        inventory_index=indice,
        catalog_id=101000001,
        item_guid=guid,
        gate_index=gate,
        apply_flag=ApplyFlag.UNLIMIT,
        apply_value=None,
        expires_at=None,
    )


async def test_colunas_e_restricoes_do_inventario(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    engine = _sync_engine(tmp_path)
    try:
        insp = inspect(engine)
        assert [c["name"] for c in insp.get_columns("account_items")] == [
            "id",
            "account_id",
            "inventory_index",
            "catalog_id",
            "item_guid",
            "account_morat_id",
            "slot_name",
            "system_slot",
            "apply_flag",
            "apply_value",
            "expires_at",
            "created_at",
            "updated_at",
        ]
        assert [c["name"] for c in insp.get_columns("account_morats")] == [
            "id",
            "account_id",
            "inventory_index",
            "catalog_id",
            "item_guid",
            "gate_index",
            "apply_flag",
            "apply_value",
            "expires_at",
            "created_at",
            "updated_at",
        ]
        colunas_contas = {c["name"] for c in insp.get_columns("accounts")}
        assert {"regular_nest_id", "regular_morat_class"} <= colunas_contas
        assert sorted(u["name"] for u in insp.get_unique_constraints("account_items")) == [
            "account_items_account_id_inventory_index_unique",
            "account_items_account_id_system_slot_unique",
            "account_items_account_morat_id_slot_name_unique",
            "account_items_item_guid_unique",
        ]
        assert sorted(u["name"] for u in insp.get_unique_constraints("account_morats")) == [
            "account_morats_account_id_gate_index_unique",
            "account_morats_account_id_inventory_index_unique",
            "account_morats_item_guid_unique",
        ]
        fks = {fk["name"]: fk for fk in insp.get_foreign_keys("account_items")}
        assert set(fks) == {
            "account_items_account_id_foreign",
            "account_items_account_morat_id_foreign",
        }
        assert fks["account_items_account_morat_id_foreign"]["options"] == {"ondelete": "SET NULL"}
    finally:
        engine.dispose()


async def test_item_preserva_expires_at_em_utc(db: async_sessionmaker[AsyncSession]) -> None:
    conta = await _conta(db, "ana", TOKEN_ANA)
    inv = SqlInventoryRepository(db)
    await inv.add_item(_item(conta.id, 1, _guid(1), PRAZO))
    await inv.add_item(_item(conta.id, 2, _guid(2), None))
    com_prazo, sem_prazo = await inv.items(conta.id)
    assert com_prazo.expires_at == PRAZO
    assert com_prazo.expires_at is not None
    assert com_prazo.expires_at.utcoffset() == timedelta(0)
    assert com_prazo.apply_flag is ApplyFlag.REALTIME
    assert sem_prazo.expires_at is None


async def test_morat_ida_e_volta(db: async_sessionmaker[AsyncSession]) -> None:
    conta = await _conta(db, "ana", TOKEN_ANA)
    inv = SqlInventoryRepository(db)
    morat = _morat(conta.id, 2, 2, _guid(10))
    await inv.add_morat(morat)
    assert [replace(m, id=None) for m in await inv.morats(conta.id)] == [morat]


async def test_inventario_e_separado_por_conta(db: async_sessionmaker[AsyncSession]) -> None:
    ana = await _conta(db, "ana", TOKEN_ANA)
    bia = await _conta(db, "bia", TOKEN_BIA)
    inv = SqlInventoryRepository(db)
    await inv.add_item(_item(ana.id, 1, _guid(1)))
    assert await inv.items(bia.id) == []


async def test_gate_repetido_levanta_conflito(db: async_sessionmaker[AsyncSession]) -> None:
    conta = await _conta(db, "ana", TOKEN_ANA)
    inv = SqlInventoryRepository(db)
    await inv.add_morat(_morat(conta.id, 2, 2, _guid(1)))
    # Só o gate repete: índice e guid são novos.
    with pytest.raises(InventoryConflict, match="gate 2"):
        await inv.add_morat(_morat(conta.id, 5, 2, _guid(2)))
    assert [m.inventory_index for m in await inv.morats(conta.id)] == [2]


async def test_morat_guid_repetido_levanta_conflito(db: async_sessionmaker[AsyncSession]) -> None:
    conta = await _conta(db, "ana", TOKEN_ANA)
    inv = SqlInventoryRepository(db)
    await inv.add_morat(_morat(conta.id, 2, 2, _guid(1)))
    # Só o guid repete: gate e índice são novos.
    with pytest.raises(InventoryConflict):
        await inv.add_morat(_morat(conta.id, 3, 3, _guid(1)))


async def test_item_indice_e_guid_repetidos_levantam_conflito(
    db: async_sessionmaker[AsyncSession],
) -> None:
    conta = await _conta(db, "ana", TOKEN_ANA)
    inv = SqlInventoryRepository(db)
    await inv.add_item(_item(conta.id, 1, _guid(1)))
    # Só o índice repete.
    with pytest.raises(InventoryConflict, match="índice 1"):
        await inv.add_item(_item(conta.id, 1, _guid(2)))
    # Só o guid repete.
    with pytest.raises(InventoryConflict):
        await inv.add_item(_item(conta.id, 2, _guid(1)))
    assert [i.inventory_index for i in await inv.items(conta.id)] == [1]


async def test_regular_padrao_zero_e_set_regular_grava(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    conta = await _conta(db, "ana", TOKEN_ANA)
    contas = SqlAccountRepository(db)
    assert await contas.regular_nest(conta.id) == 0
    await contas.set_regular(conta.id, 2, 3)
    assert await contas.regular_nest(conta.id) == 2
    engine = _sync_engine(tmp_path)
    try:
        with engine.connect() as conn:
            linha = conn.execute(
                text("SELECT regular_nest_id, regular_morat_class FROM accounts")
            ).one()
    finally:
        engine.dispose()
    assert tuple(linha) == (2, 3)
