import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def wdb_de_teste(tmp_path: Path) -> Callable[[], Path]:
    """Fábrica de `landmass.wdb` mínimo: LevelList com `levelname` em cp1252 gravado como texto,
    como no arquivo real. Não copia dados do cliente; os valores são de teste."""

    def criar() -> Path:
        path = tmp_path / "landmass.wdb"
        con = sqlite3.connect(path)
        try:
            con.execute("CREATE TABLE LevelList (level integer, exp integer, levelname text)")
            con.execute("INSERT INTO LevelList VALUES (1, 0, 'Novato')")
            # "Praça" em cp1252: P r a ç a, com ç = 0xE7.
            con.execute("INSERT INTO LevelList VALUES (2, 2800, CAST(X'507261E761' AS TEXT))")
            con.commit()
        finally:
            con.close()
        return path

    return criar
