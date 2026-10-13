"""ItemCatalog: lê só a coluna `type` de `item`, `Item_Equip` e `Morats` do wdb (SQLite)."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from landmass_emu.db.item_catalog import ItemCatalog

WDB_CLIENTE = Path("D:/landmass/cliente/system/landmass.wdb")


@pytest.fixture
def wdb(tmp_path: Path) -> Path:
    """Wdb mínimo. Em cada tabela, `value` tem bytes fora de UTF-8: ler essa coluna falharia."""
    caminho = tmp_path / "landmass.wdb"
    with closing(sqlite3.connect(caminho)) as conn:
        conn.execute("CREATE TABLE item (type TEXT, value)")
        conn.execute("CREATE TABLE Item_Equip (type TEXT, value)")
        conn.execute("CREATE TABLE Morats (type TEXT, value)")
        conn.execute("INSERT INTO item VALUES ('1', CAST(X'B0A1' AS TEXT))")
        conn.execute("INSERT INTO Item_Equip VALUES ('2', CAST(X'B0A1' AS TEXT))")
        conn.execute("INSERT INTO Morats VALUES ('101000001', CAST(X'B0A1' AS TEXT))")
        conn.commit()
    return caminho


def test_value_do_fixture_nao_decodifica(wdb: Path) -> None:
    # Prova que a leitura de `value` falharia: só assim "ler só `type`" tem efeito.
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


def test_caminho_inexistente_levanta(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="não encontrado"):
        ItemCatalog.open(tmp_path / "nao_existe.wdb")


def test_diretorio_levanta(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="não encontrado"):
        ItemCatalog.open(tmp_path)


@pytest.mark.skipif(not WDB_CLIENTE.is_file(), reason="landmass.wdb do cliente ausente")
def test_wdb_real_morats_e_item() -> None:
    catalogo = ItemCatalog.open(WDB_CLIENTE)
    assert catalogo.is_morat(101000001)
    assert catalogo.is_morat(104000001)
    assert not catalogo.is_inventory_item(101000001)
