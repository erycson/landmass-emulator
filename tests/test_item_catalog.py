"""ItemCatalog e LazyItemCatalog: ids (`type`) e vendas (`key` e `value`) de `item`, `Item_Equip` e
`Morats` do wdb (SQLite)."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from landmass_emu.db.item_catalog import ItemCatalog, LazyItemCatalog
from landmass_emu.domain.shop import Requirements, SaleInfo

WDB_CLIENTE = Path("D:/landmass/cliente/system/landmass.wdb")


def _criar_wdb(caminho: Path) -> Path:
    """Wdb mínimo com a forma EAV. Linhas sem interesse têm `value` fora de UTF-8: ler essa coluna
    falharia, por isso só as chaves de venda entram na consulta."""
    with closing(sqlite3.connect(caminho)) as conn:
        for tabela in ("item", "Item_Equip", "Morats"):
            conn.execute(f'CREATE TABLE {tabela} (type TEXT, "key" TEXT, value)')
        conn.execute("INSERT INTO item VALUES ('1', 'item_name', CAST(X'B0A1' AS TEXT))")
        conn.execute("INSERT INTO item VALUES ('1', 'item_buy_point[1]', '300')")
        conn.execute("INSERT INTO item VALUES ('1', 'item_buy_cash[1]', '30')")
        conn.execute("INSERT INTO item VALUES ('1', 'item_required_level', '2')")
        conn.execute("INSERT INTO Item_Equip VALUES ('2', 'item_name', CAST(X'B0A1' AS TEXT))")
        conn.execute("INSERT INTO Morats VALUES ('101000001', 'name', CAST(X'B0A1' AS TEXT))")
        conn.execute("INSERT INTO Morats VALUES ('101000001', 'buy_point[0]', '5000')")
        conn.execute("INSERT INTO Morats VALUES ('101000001', 'buy_cash[0]', '2000')")
        conn.commit()
    return caminho


@pytest.fixture
def wdb(tmp_path: Path) -> Path:
    return _criar_wdb(tmp_path / "landmass.wdb")


def test_value_do_fixture_nao_decodifica(wdb: Path) -> None:
    # Prova que a leitura de `value` falharia: só assim "ler só as chaves de venda" tem efeito.
    with closing(sqlite3.connect(wdb)) as conn, pytest.raises(sqlite3.OperationalError):
        conn.execute("SELECT value FROM item").fetchall()


def test_item_e_equip_entram_no_inventario(wdb: Path) -> None:
    catalogo = ItemCatalog.open(wdb)
    assert catalogo.is_inventory_item(1)
    assert catalogo.is_inventory_item(2)
    assert not catalogo.is_inventory_item(101000001)


def test_morat_so_em_morats(wdb: Path) -> None:
    catalogo = ItemCatalog.open(wdb)
    assert catalogo.is_morat(101000001)
    assert not catalogo.is_morat(1)
    assert not catalogo.is_morat(2)


def test_id_desconhecido_nao_e_item_nem_morat(wdb: Path) -> None:
    catalogo = ItemCatalog.open(wdb)
    assert not catalogo.is_inventory_item(999)
    assert not catalogo.is_morat(999)


def test_venda_de_item_tem_preco_por_opcao_e_requisito(wdb: Path) -> None:
    venda = ItemCatalog.open(wdb).sale(1)
    assert venda == SaleInfo(
        is_morat=False,
        ld=(0, 300, 0, 0),
        cash=(0, 30, 0, 0),
        requirements=Requirements(level=2),
    )


def test_venda_de_morat_usa_buy_point_e_buy_cash(wdb: Path) -> None:
    venda = ItemCatalog.open(wdb).sale(101000001)
    assert venda == SaleInfo(
        is_morat=True,
        ld=(5000, 0, 0, 0),
        cash=(2000, 0, 0, 0),
        requirements=Requirements(),
    )


def test_id_sem_chave_de_venda_nao_tem_venda(wdb: Path) -> None:
    catalogo = ItemCatalog.open(wdb)
    assert catalogo.sale(2) is None
    assert catalogo.sale(999) is None


def test_caminho_inexistente_levanta(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="não encontrado"):
        ItemCatalog.open(tmp_path / "nao_existe.wdb")


def test_diretorio_levanta(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="não encontrado"):
        ItemCatalog.open(tmp_path)


def test_lazy_nao_guarda_o_erro_de_abertura(tmp_path: Path) -> None:
    caminho = tmp_path / "landmass.wdb"
    lazy = LazyItemCatalog(caminho)
    with pytest.raises(ValueError, match="não encontrado"):
        lazy.is_inventory_item(1)
    # Depois que o wdb aparece, a próxima consulta abre e responde.
    _criar_wdb(caminho)
    assert lazy.is_inventory_item(1)
    assert lazy.sale(1) is not None


@pytest.mark.skipif(not WDB_CLIENTE.is_file(), reason="landmass.wdb do cliente ausente")
def test_wdb_real_morats_e_item() -> None:
    catalogo = ItemCatalog.open(WDB_CLIENTE)
    assert catalogo.is_morat(101000001)
    assert catalogo.is_morat(104000001)
    assert not catalogo.is_inventory_item(101000001)
    venda = catalogo.sale(101000001)
    assert venda is not None
    assert venda.ld[0] == 5000
