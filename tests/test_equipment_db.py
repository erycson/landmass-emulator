"""Montagem, destruição e prazo no SQLite real (F6, F7): troca de peça, zeragem das peças ao
destruir o morat, slot de sistema único e débito do prazo com o saldo na mesma transação."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.app import open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.equipment import SqlEquipmentRepository
from landmass_emu.db.inventory import SqlInventoryRepository
from landmass_emu.db.progression import SqlProgressionRepository
from landmass_emu.domain.account import hash_token
from landmass_emu.domain.currency import Currency
from landmass_emu.domain.inventory import ApplyFlag, ItemUnit, MoratUnit
from landmass_emu.domain.progression import Grant
from landmass_emu.ports.inventory import InventoryConflict
from landmass_emu.settings import Settings

TOKEN = "0123456789abcdef0123456789abcdef"
PRAZO = datetime(2026, 11, 1, tzinfo=UTC)
NOVO_PRAZO = datetime(2026, 12, 1, tzinfo=UTC)
PECA = 201010001
SISTEMA = 308000001
MORAT = 101000001


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


async def _conta(db: async_sessionmaker[AsyncSession], ld: int = 0) -> int:
    conta = await SqlAccountRepository(db).create("ana", "Ana", hash_token(TOKEN))
    if ld:
        await SqlProgressionRepository(db).grant(conta.id, Grant(ld=ld))
    return conta.id


def _item(conta: int, indice: int, catalogo: int = PECA, prazo: datetime = PRAZO) -> ItemUnit:
    return ItemUnit(
        account_id=conta,
        inventory_index=indice,
        catalog_id=catalogo,
        item_guid=f"{indice:036d}",
        apply_flag=ApplyFlag.REALTIME,
        apply_value=None,
        expires_at=prazo,
    )


def _morat(conta: int, gate: int) -> MoratUnit:
    return MoratUnit(
        account_id=conta,
        inventory_index=gate,
        catalog_id=MORAT,
        item_guid=f"m{gate:035d}",
        gate_index=gate,
        apply_flag=ApplyFlag.UNLIMIT,
        apply_value=None,
        expires_at=None,
    )


async def test_montar_e_desmontar_grava_morat_e_slot(
    db: async_sessionmaker[AsyncSession],
) -> None:
    conta = await _conta(db)
    inv, eq = SqlInventoryRepository(db), SqlEquipmentRepository(db)
    await inv.add_morat(_morat(conta, 0))
    morat_id = (await inv.morats(conta))[0].id
    await inv.add_item(_item(conta, 1))
    assert morat_id is not None

    await eq.mount(conta, 1, morat_id, "main_weapon")
    [montado] = await inv.items(conta)
    assert (montado.account_morat_id, montado.slot_name) == (morat_id, "main_weapon")

    await eq.unmount(conta, 1)
    [solto] = await inv.items(conta)
    assert (solto.account_morat_id, solto.slot_name) == (None, None)


async def test_montar_no_slot_ocupado_solta_a_peca_antiga(
    db: async_sessionmaker[AsyncSession],
) -> None:
    conta = await _conta(db)
    inv, eq = SqlInventoryRepository(db), SqlEquipmentRepository(db)
    await inv.add_morat(_morat(conta, 0))
    morat_id = (await inv.morats(conta))[0].id
    assert morat_id is not None
    await inv.add_item(_item(conta, 1))
    await inv.add_item(_item(conta, 2))

    await eq.mount(conta, 1, morat_id, "main_weapon")
    await eq.mount(conta, 2, morat_id, "main_weapon")

    antiga, nova = await inv.items(conta)
    assert antiga.account_morat_id is None
    assert (nova.account_morat_id, nova.slot_name) == (morat_id, "main_weapon")


async def test_destruir_morat_zera_as_pecas_e_apaga_a_linha(
    db: async_sessionmaker[AsyncSession],
) -> None:
    conta = await _conta(db)
    inv, eq = SqlInventoryRepository(db), SqlEquipmentRepository(db)
    await inv.add_morat(_morat(conta, 0))
    morat_id = (await inv.morats(conta))[0].id
    assert morat_id is not None
    await inv.add_item(_item(conta, 1))
    await eq.mount(conta, 1, morat_id, "main_weapon")

    await eq.destroy_morat(conta, morat_id)

    [peca] = await inv.items(conta)
    assert (peca.account_morat_id, peca.slot_name) == (None, None)
    assert await inv.morats(conta) == []


async def test_destruir_item_apaga_a_linha(db: async_sessionmaker[AsyncSession]) -> None:
    conta = await _conta(db)
    inv = SqlInventoryRepository(db)
    await inv.add_item(_item(conta, 1))
    await SqlEquipmentRepository(db).destroy_item(conta, 1)
    assert await inv.items(conta) == []


async def test_dois_itens_no_mesmo_slot_de_sistema_viram_conflito(
    db: async_sessionmaker[AsyncSession],
) -> None:
    conta = await _conta(db)
    inv, eq = SqlInventoryRepository(db), SqlEquipmentRepository(db)
    await inv.add_item(_item(conta, 1, SISTEMA))
    await inv.add_item(_item(conta, 2, SISTEMA))
    await eq.set_system_slot(conta, 1, 0)
    with pytest.raises(InventoryConflict):
        await eq.set_system_slot(conta, 2, 0)


async def test_estender_debita_o_saldo_e_grava_o_novo_prazo(
    db: async_sessionmaker[AsyncSession],
) -> None:
    conta = await _conta(db, ld=1000)
    inv = SqlInventoryRepository(db)
    await inv.add_item(_item(conta, 1, SISTEMA))
    assert await SqlEquipmentRepository(db).extend(conta, Currency.LD, 300, 1, NOVO_PRAZO)
    assert (await SqlProgressionRepository(db).get(conta)).ld == 700
    [item] = await inv.items(conta)
    assert item.expires_at == NOVO_PRAZO


async def test_estender_sem_saldo_nao_grava_nada(db: async_sessionmaker[AsyncSession]) -> None:
    conta = await _conta(db, ld=100)
    inv = SqlInventoryRepository(db)
    await inv.add_item(_item(conta, 1, SISTEMA))
    assert not await SqlEquipmentRepository(db).extend(conta, Currency.LD, 300, 1, NOVO_PRAZO)
    assert (await SqlProgressionRepository(db).get(conta)).ld == 100
    [item] = await inv.items(conta)
    assert item.expires_at == PRAZO
