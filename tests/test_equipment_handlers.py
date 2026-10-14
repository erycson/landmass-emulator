"""Handlers de equipar, desequipar, destruir e estender no Channel Server: serviços reais sobre o
SQLite e um `landmass.wdb` mínimo (`item`, `Item_Equip` e `Morats`). Confere opcode e campos da
resposta, inclusive a recusa (resultado ≠ 0, sem registro)."""

import sqlite3
import struct
from collections.abc import AsyncIterator
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.app import open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.catalog import WdbCatalog
from landmass_emu.db.equipment import SqlEquipmentRepository
from landmass_emu.db.inventory import SqlInventoryRepository
from landmass_emu.db.item_catalog import LazyItemCatalog
from landmass_emu.db.progression import SqlProgressionRepository
from landmass_emu.domain.account import Account, hash_token
from landmass_emu.domain.equipment import EquipService
from landmass_emu.domain.inventory import ApplyFlag, ItemUnit, MoratUnit
from landmass_emu.domain.lifecycle import DestroyService, ExtendService
from landmass_emu.domain.progression import Grant
from landmass_emu.handlers.channel.equipment import EquipmentHandlers
from landmass_emu.net.session import Session
from landmass_emu.protocol.equipment import (
    CsItemDestroyOut,
    CsItemExtendOut,
    CsItemUnusedPieceOut,
    CsItemUsedPieceOut,
    CsItemUsedRefusedOut,
    CsItemUsedSystemOut,
    CsMoratsDestroyOut,
)
from landmass_emu.settings import Settings

TOKEN = "0123456789abcdef0123456789abcdef"
PECA = 201010001  # Item_Equip: slot 0 (main_weapon), classe 1111
SISTEMA = 308000001  # item de sistema, à venda por 300 LD na opção 1
MORAT = 101000001  # Morats: classe 1 (Assault)


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


def _wdb(tmp_path: Path) -> Path:
    caminho = tmp_path / "landmass.wdb"
    with closing(sqlite3.connect(caminho)) as conn:
        for tabela in ("item", "Item_Equip", "Morats"):
            conn.execute(f'CREATE TABLE {tabela} (type TEXT, "key" TEXT, value)')
        linhas = {
            "Item_Equip": [("item_slot", "0"), ("item_required_class", "1111")],
            "item": [("item_buy_point[1]", "300"), ("item_buy_cash[1]", "30")],
            "Morats": [
                ("required_class", "1"),
                ("power", "138"),
                ("strength", "185"),
                ("agility", "185"),
                ("precision", "200"),
            ],
        }
        for tabela, pares in linhas.items():
            ids = PECA if tabela == "Item_Equip" else SISTEMA if tabela == "item" else MORAT
            conn.executemany(
                f"INSERT INTO {tabela} VALUES (?, ?, ?)",
                [(str(ids), chave, valor) for chave, valor in pares],
            )
        conn.commit()
    return caminho


async def _cenario(
    db: async_sessionmaker[AsyncSession], tmp_path: Path, ld: int = 1000
) -> tuple[EquipmentHandlers, Session, Account]:
    conta = await SqlAccountRepository(db).create("ana", "Ana", hash_token(TOKEN))
    await SqlProgressionRepository(db).grant(conta.id, Grant(ld=ld))
    wdb = _wdb(tmp_path)
    catalogo = LazyItemCatalog(wdb)
    inv = SqlInventoryRepository(db)
    eq = SqlEquipmentRepository(db)
    progresso = SqlProgressionRepository(db)
    handlers = EquipmentHandlers(
        equip=EquipService(
            catalog=catalogo,
            levels=WdbCatalog(wdb),
            inventory=inv,
            equipment=eq,
            accounts=SqlAccountRepository(db),
            progression=progresso,
        ),
        destroy=DestroyService(inventory=inv, equipment=eq),
        extend=ExtendService(catalog=catalogo, inventory=inv, equipment=eq, progression=progresso),
    )
    return handlers, Session(peer="t", account=conta), conta


def _item(conta: int, indice: int, catalogo: int, prazo: datetime | None = None) -> ItemUnit:
    return ItemUnit(
        account_id=conta,
        inventory_index=indice,
        catalog_id=catalogo,
        item_guid=f"{indice:036d}",
        apply_flag=ApplyFlag.REALTIME,
        apply_value=None,
        expires_at=prazo or datetime.now(UTC) + timedelta(days=5),
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


async def test_equipar_peca_responde_562_com_gate_indice_e_slot(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    handlers, sessao, conta = await _cenario(db, tmp_path)
    await SqlInventoryRepository(db).add_morat(_morat(conta.id, 0))
    await SqlInventoryRepository(db).add_item(_item(conta.id, 1, PECA))

    respostas = await handlers.item_used(sessao, struct.pack("<HHi", 1, 0, 0))

    assert respostas == [CsItemUsedPieceOut(gate=0, index=1, slot=0, result=0)]


async def test_gate_vazio_responde_561_com_no_gate(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    handlers, sessao, conta = await _cenario(db, tmp_path)
    await SqlInventoryRepository(db).add_item(_item(conta.id, 1, PECA))

    respostas = await handlers.item_used(sessao, struct.pack("<HHi", 1, 0, 0))

    assert respostas == [CsItemUsedRefusedOut(-1)]


async def test_valor_por_valor_fica_fora_do_f6_e_responde_561(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    handlers, sessao, conta = await _cenario(db, tmp_path)
    await SqlInventoryRepository(db).add_item(_item(conta.id, 1, PECA))

    respostas = await handlers.item_used(sessao, struct.pack("<HHi", 1, 0, 7))

    assert respostas == [CsItemUsedRefusedOut(-4)]


async def test_item_de_sistema_responde_554_com_o_slot(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    handlers, sessao, conta = await _cenario(db, tmp_path)
    await SqlInventoryRepository(db).add_item(_item(conta.id, 2, SISTEMA))

    [resposta] = await handlers.item_used(sessao, struct.pack("<HHi", 2, 0, 0))

    assert isinstance(resposta, CsItemUsedSystemOut)
    assert (resposta.slot, resposta.result) == (0, 0)


async def test_desequipar_responde_572_com_gate_e_slot(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    handlers, sessao, conta = await _cenario(db, tmp_path)
    await SqlInventoryRepository(db).add_morat(_morat(conta.id, 0))
    await SqlInventoryRepository(db).add_item(_item(conta.id, 1, PECA))
    await handlers.item_used(sessao, struct.pack("<HHi", 1, 0, 0))

    respostas = await handlers.item_unused(sessao, struct.pack("<HH", 1, 0))

    assert respostas == [CsItemUnusedPieceOut(gate=0, slot=0, result=0)]


async def test_destruir_ultimo_morat_responde_556_com_recusa(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    handlers, sessao, conta = await _cenario(db, tmp_path)
    await SqlInventoryRepository(db).add_morat(_morat(conta.id, 0))

    respostas = await handlers.item_destroy(sessao, struct.pack("<iH", MORAT, 0))

    assert respostas == [CsItemDestroyOut(index=0, gate=0, mounted=False, result=-4)]


async def test_destruir_morat_com_outro_responde_557(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    handlers, sessao, conta = await _cenario(db, tmp_path)
    await SqlInventoryRepository(db).add_morat(_morat(conta.id, 0))
    await SqlInventoryRepository(db).add_morat(_morat(conta.id, 1))

    respostas = await handlers.item_destroy(sessao, struct.pack("<iH", MORAT, 0))

    assert respostas == [CsMoratsDestroyOut(gate=0, result=0)]


async def test_estender_item_responde_582_com_prazo_e_saldo_restante(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    handlers, sessao, conta = await _cenario(db, tmp_path, ld=1000)
    await SqlInventoryRepository(db).add_item(_item(conta.id, 1, SISTEMA))

    [resposta] = await handlers.item_extend(sessao, struct.pack("<iHBB", SISTEMA, 1, 1, 1))

    assert isinstance(resposta, CsItemExtendOut)
    assert (resposta.index, resposta.point, resposta.cash, resposta.result) == (1, 700, 0, 0)
    # Parte de agora (o item ainda vale, então soma a partir do prazo de 5 dias): 12 dias.
    assert resposta.apply_value > int((datetime.now(UTC) + timedelta(days=11)).timestamp())


async def test_estender_morat_responde_582_com_recusa(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    handlers, sessao, conta = await _cenario(db, tmp_path)
    await SqlInventoryRepository(db).add_morat(_morat(conta.id, 0))

    [resposta] = await handlers.item_extend(sessao, struct.pack("<iHBB", MORAT, 0, 1, 1))

    assert resposta == CsItemExtendOut(index=0, apply_value=0, cash=0, point=0, result=-4)


async def test_sem_login_o_pedido_e_ignorado(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    handlers, _, _ = await _cenario(db, tmp_path)
    assert await handlers.item_used(Session(peer="t"), struct.pack("<HHi", 1, 0, 0)) == []
