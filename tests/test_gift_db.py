"""Depósito e Item Surpresa no SQLite real: envio com débito na mesma transação, resgate que grava o
item ou desfaz tudo, e consumo do gacha com crédito de LD e contagem de gates (F10, F11, D20)."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.app import open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.gifts import SqlGiftRepository
from landmass_emu.db.inventory import SqlInventoryRepository
from landmass_emu.db.progression import SqlProgressionRepository
from landmass_emu.db.use import SqlUseRepository
from landmass_emu.domain.account import hash_token
from landmass_emu.domain.currency import Currency
from landmass_emu.domain.inventory import ApplyFlag, ItemUnit
from landmass_emu.domain.progression import Grant
from landmass_emu.ports.inventory import InventoryConflict
from landmass_emu.settings import Settings

TOKEN_ANA = "0123456789abcdef0123456789abcdef"
TOKEN_BIA = "fedcba9876543210fedcba9876543210"
PRAZO = datetime(2026, 11, 1, tzinfo=UTC)
ITEM = 201020001
GACHA = 308010006


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


async def _contas(db: async_sessionmaker[AsyncSession], ld: int) -> tuple[int, int]:
    contas = SqlAccountRepository(db)
    ana = await contas.create("ana", "Ana", hash_token(TOKEN_ANA))
    bia = await contas.create("bia", "Bia", hash_token(TOKEN_BIA))
    if ld:  # Grant recusa tudo zero
        await SqlProgressionRepository(db).grant(ana.id, Grant(ld=ld, cash=0))
    return ana.id, bia.id


def _item(conta: int, indice: int, guid: str, catalog: int = ITEM) -> ItemUnit:
    return ItemUnit(
        account_id=conta,
        inventory_index=indice,
        catalog_id=catalog,
        item_guid=guid,
        apply_flag=ApplyFlag.REALTIME,
        apply_value=None,
        expires_at=PRAZO,
    )


async def test_envio_debita_o_remetente_e_a_pagina_lista_o_presente(
    db: async_sessionmaker[AsyncSession],
) -> None:
    ana, bia = await _contas(db, ld=1000)
    gifts = SqlGiftRepository(db)
    assert await gifts.send(ana, bia, Currency.LD, 300, ITEM, 7) is True
    assert await gifts.send(ana, bia, Currency.LD, 300, ITEM, 1) is True
    assert (await SqlProgressionRepository(db).get(ana)).ld == 400
    pagina = await gifts.page(bia, 0, 12)
    assert [(g.slot, g.sender_account_id, g.catalog_id, g.duration_days) for g in pagina] == [
        (1, ana, ITEM, 7),
        (2, ana, ITEM, 1),
    ]


async def test_saldo_insuficiente_nao_grava_presente(db: async_sessionmaker[AsyncSession]) -> None:
    ana, bia = await _contas(db, ld=100)
    gifts = SqlGiftRepository(db)
    assert await gifts.send(ana, bia, Currency.LD, 300, ITEM, 7) is False
    assert (await SqlProgressionRepository(db).get(ana)).ld == 100
    assert await gifts.page(bia, 0, 12) == []


async def test_resgate_grava_o_item_e_nao_repete(db: async_sessionmaker[AsyncSession]) -> None:
    ana, bia = await _contas(db, ld=1000)
    gifts = SqlGiftRepository(db)
    await gifts.send(ana, bia, Currency.LD, 300, ITEM, 7)
    presente = (await gifts.page(bia, 0, 12))[0]
    assert await gifts.claim(presente, _item(bia, 1, "1" * 36)) is True
    assert [i.inventory_index for i in await SqlInventoryRepository(db).items(bia)] == [1]
    assert await gifts.pending(bia, 1) is None
    assert await gifts.claim(presente, _item(bia, 2, "2" * 36)) is False
    assert len(await SqlInventoryRepository(db).items(bia)) == 1


async def test_indice_ocupado_no_resgate_mantem_o_presente_pendente(
    db: async_sessionmaker[AsyncSession],
) -> None:
    ana, bia = await _contas(db, ld=1000)
    gifts = SqlGiftRepository(db)
    await gifts.send(ana, bia, Currency.LD, 300, ITEM, 7)
    await SqlInventoryRepository(db).add_item(_item(bia, 1, "1" * 36))
    presente = (await gifts.page(bia, 0, 12))[0]
    with pytest.raises(InventoryConflict):
        await gifts.claim(presente, _item(bia, 1, "3" * 36))
    assert await gifts.pending(bia, 1) is not None
    assert len(await SqlInventoryRepository(db).items(bia)) == 1


async def test_consumo_do_gacha_credita_ld_e_troca_o_item(
    db: async_sessionmaker[AsyncSession],
) -> None:
    ana, _ = await _contas(db, ld=0)
    await SqlInventoryRepository(db).add_item(_item(ana, 3, "1" * 36, catalog=GACHA))
    usos = SqlUseRepository(db)
    premio = _item(ana, 4, "2" * 36)
    assert await usos.consume(ana, 3, GACHA, ld=5000, grants=(premio,), gate_count=None) is True
    assert (await SqlProgressionRepository(db).get(ana)).ld == 5000
    assert [i.inventory_index for i in await SqlInventoryRepository(db).items(ana)] == [4]


async def test_consumo_com_premio_em_indice_ocupado_desfaz_tudo(
    db: async_sessionmaker[AsyncSession],
) -> None:
    ana, _ = await _contas(db, ld=0)
    inventario = SqlInventoryRepository(db)
    await inventario.add_item(_item(ana, 3, "1" * 36, catalog=GACHA))
    await inventario.add_item(_item(ana, 4, "2" * 36))
    with pytest.raises(InventoryConflict):
        await SqlUseRepository(db).consume(
            ana, 3, GACHA, ld=5000, grants=(_item(ana, 4, "3" * 36),), gate_count=None
        )
    assert (await SqlProgressionRepository(db).get(ana)).ld == 0
    assert [i.inventory_index for i in await inventario.items(ana)] == [3, 4]


async def test_consumo_de_indice_inexistente_nao_credita(
    db: async_sessionmaker[AsyncSession],
) -> None:
    ana, _ = await _contas(db, ld=0)
    assert (
        await SqlUseRepository(db).consume(ana, 9, GACHA, ld=5000, grants=(), gate_count=None)
        is False
    )
    assert (await SqlProgressionRepository(db).get(ana)).ld == 0


async def test_adicionar_hangar_grava_a_nova_contagem_de_gates(
    db: async_sessionmaker[AsyncSession],
) -> None:
    ana, _ = await _contas(db, ld=0)
    await SqlInventoryRepository(db).add_item(_item(ana, 5, "1" * 36, catalog=308010005))
    assert await SqlUseRepository(db).consume(ana, 5, 308010005, ld=0, grants=(), gate_count=5)
    assert await SqlAccountRepository(db).gate_count(ana) == 5
