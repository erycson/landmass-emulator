"""Atalhos da conta (`account_quick_slots`) no SQLite: os 5 slots padrão, sem duplicar, e o kit que
os semeia na criação e no `account kit apply`."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.admin_inventory import StarterKitAdmin
from landmass_emu.app import open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.inventory import SqlInventoryRepository
from landmass_emu.db.quick_slots import SqlQuickSlotRepository
from landmass_emu.domain.account import hash_token
from landmass_emu.domain.quick_slots import DEFAULT_QUICK_SLOTS
from landmass_emu.settings import Settings

TOKEN = "0123456789abcdef0123456789abcdef"


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


class KitVazio:
    """Kit sem morats: o teste só olha os atalhos."""

    def plan(self, account_id: int, used: list[int | None]) -> list[object]:
        return []


async def test_semeadura_grava_os_cinco_slots_e_nao_duplica(
    db: async_sessionmaker[AsyncSession],
) -> None:
    conta = await SqlAccountRepository(db).create("ana", "Ana", hash_token(TOKEN))
    atalhos = SqlQuickSlotRepository(db)
    assert await atalhos.seed(conta.id, DEFAULT_QUICK_SLOTS) == 5
    assert await atalhos.seed(conta.id, DEFAULT_QUICK_SLOTS) == 0
    assert await atalhos.slots(conta.id) == list(DEFAULT_QUICK_SLOTS)


async def test_kit_aplicado_semeia_os_atalhos_da_conta(
    db: async_sessionmaker[AsyncSession],
) -> None:
    conta = await SqlAccountRepository(db).create("ana", "Ana", hash_token(TOKEN))
    admin = StarterKitAdmin(
        SqlAccountRepository(db),
        SqlInventoryRepository(db),
        KitVazio(),
        SqlQuickSlotRepository(db),
    )
    await admin.apply("ana")
    await admin.apply("ana")  # reaplicar o kit não duplica os atalhos
    assert len(await SqlQuickSlotRepository(db).slots(conta.id)) == 5
