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
            # `maps` mínimo: RecordIndex é texto, como no arquivo real. Valores de teste.
            con.execute(
                "CREATE TABLE maps (RecordIndex varchar(2), MapFileName varchar(128), "
                "PlayerCountMax integer, OPType integer)"
            )
            con.execute("INSERT INTO maps VALUES ('00', 'ONS-AirPort', 24, 0)")
            con.execute("INSERT INTO maps VALUES ('01', 'ONS-Treino', 32, 0)")
            con.commit()
        finally:
            con.close()
        return path

    return criar
