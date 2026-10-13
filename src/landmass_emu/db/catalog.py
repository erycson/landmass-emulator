"""Dados estáticos do cliente lidos de `landmass.wdb` em modo somente leitura (D7, D19).

Hoje só a `LevelList` (patente). O arquivo é SQLite com textos em cp1252.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

from landmass_emu.domain.progression import Level


class WdbCatalog:
    def __init__(self, path: Path) -> None:
        self._path = path

    def level_list(self) -> tuple[Level, ...]:
        if not self._path.is_file():
            raise ValueError(f"landmass.wdb não encontrado em {self._path}")
        uri = f"{self._path.resolve().as_uri()}?mode=ro"
        try:
            with closing(sqlite3.connect(uri, uri=True)) as con:
                con.text_factory = self._decode
                rows = con.execute(
                    "SELECT level, exp, levelname FROM LevelList ORDER BY level"
                ).fetchall()
        except sqlite3.Error as e:
            raise ValueError(f"landmass.wdb ilegível: {e}") from e
        return tuple(Level(level=int(lv), exp=int(exp), name=str(name)) for lv, exp, name in rows)

    @staticmethod
    def _decode(raw: bytes) -> str:
        return raw.decode("cp1252")
