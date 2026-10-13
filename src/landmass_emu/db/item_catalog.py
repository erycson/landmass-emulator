"""Catálogo do cliente: `landmass.wdb` (SQLite), aberto só em leitura. Implementa `Catalog`.

Formato EAV: a coluna `type` de `item`, `Item_Equip` e `Morats` é o id do catálogo. Só essa coluna
é lida, porque `value` tem texto fora de UTF-8 (`sqlite3` falharia ao decodificá-la).
"""

import sqlite3
from contextlib import closing
from pathlib import Path


class ItemCatalog:
    """Ids do catálogo em memória. Carregado uma vez; a CLI usa, o Channel ainda não."""

    def __init__(self, inventory_items: frozenset[int], morats: frozenset[int]) -> None:
        self._inventory_items = inventory_items
        self._morats = morats

    @classmethod
    def open(cls, path: Path) -> ItemCatalog:
        if not path.is_file():
            raise ValueError(f"catálogo do cliente não encontrado: {path}")
        uri = f"{path.resolve().as_uri()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as conn:
            # Item (grupo 3) e Item_Equip (grupo 2) vão para o inventário; Morats (grupo 1), não.
            items = _type_ids(conn, "item") | _type_ids(conn, "Item_Equip")
            morats = _type_ids(conn, "Morats")
        return cls(frozenset(items), frozenset(morats))

    def is_inventory_item(self, catalog_id: int) -> bool:
        return catalog_id in self._inventory_items

    def is_morat(self, catalog_id: int) -> bool:
        return catalog_id in self._morats


def _type_ids(conn: sqlite3.Connection, table: str) -> set[int]:
    # `table` é sempre uma constante deste módulo, nunca entrada externa.
    rows = conn.execute(f"SELECT DISTINCT type FROM {table} WHERE type IS NOT NULL")
    return {int(row[0]) for row in rows if str(row[0]).isdigit()}
