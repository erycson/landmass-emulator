"""CLI da loja (D191) sobre SQLite real: sync do wdb de teste, habilitar, desativar, preço, listagem
e o aviso de loja vazia na subida. O wdb é montado aqui, com valores de teste."""

import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import closing
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.__main__ import Cli, _parser
from landmass_emu.admin_shop import ShopAdmin
from landmass_emu.app import open_database, warn_empty_shop
from landmass_emu.db.item_catalog import ItemCatalog
from landmass_emu.db.shop import SqlShopItemRepository
from landmass_emu.ports.shop import ShopItem
from landmass_emu.settings import Settings


def _wdb(caminho: Path) -> Path:
    """Wdb mínimo com a forma EAV. Vendas: item 1000100 (Cash no nível 1), peça 201010001 (Cash no
    nível 0), morat 101000001 (LD 1000 no nível 0, que vira 5000), item 307010001 (só LD). O item
    1000200 tem só requisito: não se vende, então não entra."""
    with closing(sqlite3.connect(caminho)) as conn:
        for tabela in ("item", "Item_Equip", "Morats"):
            conn.execute(f'CREATE TABLE {tabela} (type TEXT, "key" TEXT, value)')
        itens = [
            ("1000100", "item_name", "Wood"),
            ("1000100", "item_buy_cash[1]", "30"),
            ("1000200", "item_name", "Gancho"),
            ("1000200", "item_required_level", "2"),
            ("307010001", "item_name", "Desert"),
            ("307010001", "item_buy_point[0]", "100"),
        ]
        conn.executemany("INSERT INTO item VALUES (?, ?, ?)", itens)
        conn.execute("INSERT INTO Item_Equip VALUES ('201010001', 'item_name', 'AW-A11')")
        conn.execute("INSERT INTO Item_Equip VALUES ('201010001', 'item_buy_cash[0]', '1103')")
        morats = [
            ("101000001", "alias", "Fairy"),
            ("101000001", "buy_point[0]", "1000"),
            ("101000001", "buy_cash[0]", "3000"),
        ]
        conn.executemany("INSERT INTO Morats VALUES (?, ?, ?)", morats)
        conn.commit()
    return caminho


def _settings(tmp_path: Path, client_dir: Path | None = None) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
        client_dir=client_dir or tmp_path,
    )


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with open_database(_settings(tmp_path)) as sessoes:
        yield sessoes


async def test_sync_importa_so_as_vendas_com_nome_e_preco_do_wdb(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    catalogo = ItemCatalog.open(_wdb(tmp_path / "landmass.wdb"))
    loja = SqlShopItemRepository(db)
    texto = await ShopAdmin(loja).sync(catalogo)

    assert texto == "loja: 4 vendas do cliente (4 novas, 0 atualizadas)"
    assert await loja.get(1000200) is None  # só requisito, não se vende
    assert await loja.get(101000001) == ShopItem(
        101000001, "Fairy", True, (5000, 0, 0, 0), (3000, 0, 0, 0)
    )
    assert await loja.get(307010001) == ShopItem(
        307010001, "Desert", True, (100, 0, 0, 0), (0, 0, 0, 0)
    )


async def test_sync_de_novo_mantem_o_desativado_e_atualiza_so_nome_e_preco(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    catalogo = ItemCatalog.open(_wdb(tmp_path / "landmass.wdb"))
    admin = ShopAdmin(SqlShopItemRepository(db))
    await admin.sync(catalogo)
    assert await admin.disable(1000100) == "item 1000100 desativado na loja"

    assert await admin.sync(catalogo) == "loja: 4 vendas do cliente (0 novas, 4 atualizadas)"
    atual = await SqlShopItemRepository(db).get(1000100)
    assert atual is not None
    assert atual.enabled is False


async def test_preco_muda_um_nivel_e_mantem_o_resto(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    admin = ShopAdmin(SqlShopItemRepository(db))
    await admin.sync(ItemCatalog.open(_wdb(tmp_path / "landmass.wdb")))

    texto = await admin.price(1000100, 1, ld=None, cash=50)
    assert texto == "item 1000100, nível 1: LD 0, Cash 50"
    assert await admin.price(1000100, 2, ld=700, cash=None) == (
        "item 1000100, nível 2: LD 700, Cash 0"
    )
    atual = await SqlShopItemRepository(db).get(1000100)
    assert atual is not None
    assert (atual.ld, atual.cash) == ((0, 0, 700, 0), (0, 50, 0, 0))


async def test_preco_recusa_entrada_invalida_sem_gravar(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    admin = ShopAdmin(SqlShopItemRepository(db))
    await admin.sync(ItemCatalog.open(_wdb(tmp_path / "landmass.wdb")))

    with pytest.raises(ValueError, match="nível"):
        await admin.price(1000100, 4, ld=1, cash=None)
    with pytest.raises(ValueError, match="informe"):
        await admin.price(1000100, 0, ld=None, cash=None)
    with pytest.raises(ValueError, match="negativo"):
        await admin.price(1000100, 0, ld=-5, cash=None)
    with pytest.raises(ValueError, match="não está na loja"):
        await admin.price(999, 0, ld=1, cash=None)
    with pytest.raises(ValueError, match="não está na loja"):
        await admin.enable(999)
    atual = await SqlShopItemRepository(db).get(1000100)
    assert atual is not None
    assert atual.cash == (0, 30, 0, 0)


async def test_listagem_mostra_status_e_filtra_os_desativados(
    db: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    admin = ShopAdmin(SqlShopItemRepository(db))
    assert "loja vazia" in await admin.list_items(disabled_only=False)

    await admin.sync(ItemCatalog.open(_wdb(tmp_path / "landmass.wdb")))
    assert await admin.list_items(disabled_only=True) == "nenhum item desativado"
    await admin.disable(307010001)

    tabela = await admin.list_items(disabled_only=False)
    assert "Fairy" in tabela
    assert "5000/0/0/0" in tabela  # morat já com o ×5 gravado
    assert "desativado" in tabela
    filtrada = await admin.list_items(disabled_only=True)
    assert "Desert" in filtrada
    assert "Fairy" not in filtrada


async def test_cli_shop_list_funciona_sem_o_cliente(tmp_path: Path) -> None:
    # `shop list` não lê o wdb: funciona mesmo com o cliente fora do lugar.
    cli = Cli(_settings(tmp_path, client_dir=tmp_path / "sem_cliente"))
    args = _parser().parse_args(["shop", "list"])
    assert "loja vazia" in await cli.shop(args)


async def test_cli_shop_sync_enable_disable_price_e_list(tmp_path: Path) -> None:
    _wdb(tmp_path / "landmass.wdb")
    cli = Cli(_settings(tmp_path))
    parser = _parser()

    sync = await cli.shop(parser.parse_args(["shop", "sync"]))
    assert sync.startswith("loja: 4 vendas")
    assert await cli.shop(parser.parse_args(["shop", "disable", "1000100"])) == (
        "item 1000100 desativado na loja"
    )
    assert await cli.shop(parser.parse_args(["shop", "enable", "1000100"])) == (
        "item 1000100 habilitado na loja"
    )
    assert await cli.shop(parser.parse_args(["shop", "price", "1000100", "0", "--point", "9"])) == (
        "item 1000100, nível 0: LD 9, Cash 0"
    )
    listagem = await cli.shop(parser.parse_args(["shop", "list", "--disabled"]))
    assert listagem == "nenhum item desativado"


async def test_cli_shop_sync_sem_wdb_nao_migra_nem_grava(tmp_path: Path) -> None:
    cli = Cli(_settings(tmp_path, client_dir=tmp_path / "sem_cliente"))
    with pytest.raises(ValueError, match="não encontrado"):
        await cli.shop(_parser().parse_args(["shop", "sync"]))
    assert not (tmp_path / "landmass.db").exists()


def test_parser_recusa_nivel_fora_de_0_a_3() -> None:
    with pytest.raises(SystemExit):
        _parser().parse_args(["shop", "price", "1000100", "4", "--cash", "1"])


async def test_aviso_de_loja_vazia_na_subida(
    db: async_sessionmaker[AsyncSession], caplog: pytest.LogCaptureFixture
) -> None:
    loja = SqlShopItemRepository(db)
    with caplog.at_level(logging.WARNING):
        await warn_empty_shop(loja)
    assert "loja vazia" in caplog.text

    caplog.clear()
    await loja.sync([ShopItem(1000100, "Wood", True, (0, 0, 0, 0), (0, 30, 0, 0))])
    with caplog.at_level(logging.WARNING):
        await warn_empty_shop(loja)
    assert "loja vazia" not in caplog.text
