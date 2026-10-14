"""Dados estáticos do cliente lidos de `landmass.wdb` em modo somente leitura (D7, D19).

Hoje só a `LevelList` (patente). O arquivo é SQLite com textos em cp1252.
"""

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from landmass_emu.domain.match import MapRecord
from landmass_emu.domain.progression import Level


class WdbCatalog:
    def __init__(self, path: Path) -> None:
        self._path = path

    def level_list(self) -> tuple[Level, ...]:
        rows = self._query("SELECT level, exp, levelname FROM LevelList ORDER BY level")
        return tuple(Level(level=int(lv), exp=int(exp), name=str(name)) for lv, exp, name in rows)

    def get(self, record_id: int) -> MapRecord | None:
        """Linha de `maps` com `RecordIndex` igual a `record_id`. A coluna é texto ('00', '01')."""
        rows = self._query(
            "SELECT MapFileName, PlayerCountMax, OPType FROM maps "
            "WHERE CAST(RecordIndex AS INTEGER) = ?",
            (record_id,),
        )
        if not rows:
            return None
        file_name, player_max, op_type = rows[0]
        return MapRecord(
            record_id=record_id,
            file_name=str(file_name),
            player_max=int(player_max or 0),
            op_type=int(op_type or 0),
        )

    def _query(self, sql: str, params: tuple[object, ...] = ()) -> list[tuple[Any, ...]]:
        if not self._path.is_file():
            raise ValueError(f"landmass.wdb não encontrado em {self._path}")
        uri = f"{self._path.resolve().as_uri()}?mode=ro"
        try:
            with closing(sqlite3.connect(uri, uri=True)) as con:
                con.text_factory = self._decode
                return con.execute(sql, params).fetchall()
        except sqlite3.Error as e:
            raise ValueError(f"landmass.wdb ilegível: {e}") from e

    @staticmethod
    def _decode(raw: bytes) -> str:
        return raw.decode("cp1252")
