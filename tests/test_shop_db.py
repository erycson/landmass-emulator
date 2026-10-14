"""Débito e criação da compra no SQLite real (R-DEB-01): mesma transação, sem gravar com saldo
insuficiente e sem manter o débito quando o índice conflita."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.app import open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.inventory import SqlInventoryRepository
from landmass_emu.db.progression import SqlProgressionRepository
from landmass_emu.db.shop import SqlShopItemRepository, SqlShopRepository
from landmass_emu.domain.account import hash_token
from landmass_emu.domain.currency import Currency
from landmass_emu.domain.inventory import ApplyFlag, ItemUnit, MoratUnit
from landmass_emu.domain.progression import Grant
from landmass_emu.ports.inventory import InventoryConflict
from landmass_emu.ports.shop import ShopItem
from landmass_emu.settings import Settings

TOKEN = "0123456789abcdef0123456789abcdef"
PRAZO = datetime(2026, 11, 1, tzinfo=UTC)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
        client_dir=tmp_path,
    )


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with open_database(_settings(tmp_path)) as sessoes:
        yield sessoes


async def _conta_com_saldo(db: async_sessionmaker[AsyncSession], ld: int, cash: int) -> int:
    conta = await SqlAccountRepository(db).create("ana", "Ana", hash_token(TOKEN))
    await SqlProgressionRepository(db).grant(conta.id, Grant(ld=ld, cash=cash))
    return conta.id


def _item(conta: int, indice: int = 1, guid: str = "1" * 36) -> ItemUnit:
    return ItemUnit(
        account_id=conta,
        inventory_index=indice,
        catalog_id=1000100,
        item_guid=guid,
        apply_flag=ApplyFlag.REALTIME,
        apply_value=None,
        expires_at=PRAZO,
    )


async def test_compra_debita_o_saldo_e_grava_o_item(
    db: async_sessionmaker[AsyncSession],
) -> None:
    conta = await _conta_com_saldo(db, ld=1000, cash=0)
    assert await SqlShopRepository(db).purchase(conta, Currency.LD, 300, _item(conta)) is True
    assert (await SqlProgressionRepository(db).get(conta)).ld == 700
    itens = await SqlInventoryRepository(db).items(conta)
    assert [i.inventory_index for i in itens] == [1]
    assert itens[0].expires_at == PRAZO


async def test_saldo_insuficiente_nao_grava_nada(db: async_sessionmaker[AsyncSession]) -> None:
    conta = await _conta_com_saldo(db, ld=100, cash=0)
    assert await SqlShopRepository(db).purchase(conta, Currency.LD, 300, _item(conta)) is False
    assert (await SqlProgressionRepository(db).get(conta)).ld == 100
    assert await SqlInventoryRepository(db).items(conta) == []


async def test_morat_debita_cash_e_grava_no_gate(db: async_sessionmaker[AsyncSession]) -> None:
    conta = await _conta_com_saldo(db, ld=0, cash=2000)
    morat = MoratUnit(
        account_id=conta,
        inventory_index=2,
        catalog_id=101000001,
        item_guid="2" * 36,
        gate_index=2,
        apply_flag=ApplyFlag.UNLIMIT,
        apply_value=None,
        expires_at=None,
    )
    assert await SqlShopRepository(db).purchase(conta, Currency.CASH, 2000, morat) is True
    assert (await SqlProgressionRepository(db).get(conta)).cash == 0
    assert [m.gate_index for m in await SqlInventoryRepository(db).morats(conta)] == [2]


async def test_indice_repetido_desfaz_o_debito(db: async_sessionmaker[AsyncSession]) -> None:
    conta = await _conta_com_saldo(db, ld=1000, cash=0)
    await SqlInventoryRepository(db).add_item(_item(conta, indice=1, guid="1" * 36))
    with pytest.raises(InventoryConflict):
        await SqlShopRepository(db).purchase(
            conta, Currency.LD, 300, _item(conta, indice=1, guid="3" * 36)
        )
    assert (await SqlProgressionRepository(db).get(conta)).ld == 1000
    assert len(await SqlInventoryRepository(db).items(conta)) == 1


async def test_sync_insere_novos_habilitados_e_mantem_enabled_de_quem_existe(
    db: async_sessionmaker[AsyncSession],
) -> None:
    loja = SqlShopItemRepository(db)
    assert await loja.count() == 0
    novo = ShopItem(1000100, "Wood", True, (100, 300, 500, 900), (10, 30, 50, 90))
    assert await loja.sync([novo]) == (1, 0)

    assert await loja.set_enabled(1000100, False) is True
    renomeado = ShopItem(1000100, "Madeira", True, (100, 0, 0, 0), (20, 0, 0, 0))
    assert await loja.sync([renomeado, ShopItem(2, "Bic", True, (0, 0, 0, 0), (5, 0, 0, 0))]) == (
        1,
        1,
    )

    atual = await loja.get(1000100)
    assert atual == ShopItem(1000100, "Madeira", False, (100, 0, 0, 0), (20, 0, 0, 0))
    assert await loja.get(2) == ShopItem(2, "Bic", True, (0, 0, 0, 0), (5, 0, 0, 0))
    assert [i.catalog_id for i in await loja.all_items()] == [2, 1000100]


async def test_set_enabled_e_set_prices_recusam_id_ausente(
    db: async_sessionmaker[AsyncSession],
) -> None:
    loja = SqlShopItemRepository(db)
    assert await loja.set_enabled(9, True) is False
    assert await loja.set_prices(9, (1, 0, 0, 0), (0, 0, 0, 0)) is False
    assert await loja.get(9) is None


async def test_set_prices_grava_os_quatro_niveis(db: async_sessionmaker[AsyncSession]) -> None:
    loja = SqlShopItemRepository(db)
    await loja.sync([ShopItem(1000100, "Wood", True, (0, 0, 0, 0), (0, 0, 0, 0))])
    assert await loja.set_prices(1000100, (1, 2, 3, 4), (5, 6, 7, 8)) is True
    assert await loja.get(1000100) == ShopItem(1000100, "Wood", True, (1, 2, 3, 4), (5, 6, 7, 8))
