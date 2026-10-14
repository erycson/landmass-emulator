"""Catálogo do cliente: `landmass.wdb` (SQLite), só leitura. Implementa `Catalog` e `SaleCatalog`.

Formato EAV: a coluna `type` de `item`, `Item_Equip` e `Morats` é o id do catálogo, e `key` é o nome
do campo (preço `buy_point[i]`/`buy_cash[i]`, requisito `required_*`, com prefixo `item_` nas
tabelas de item). Só essas chaves são lidas: `value` tem texto fora de UTF-8 em outras linhas.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

from landmass_emu.domain.shop import Requirements, SaleInfo

# (tabela, prefixo do nome do campo, é morat). `table` e `prefix` são constantes deste módulo.
_SALE_TABLES: tuple[tuple[str, str, bool], ...] = (
    ("item", "item_", False),
    ("Item_Equip", "item_", False),
    ("Morats", "", True),
)
# Nomes já sem prefixo. Os demais campos do wdb são ignorados, inclusive os de texto.
_SALE_NAMES = frozenset(
    {
        *(f"buy_point[{i}]" for i in range(4)),
        *(f"buy_cash[{i}]" for i in range(4)),
        "required_level",
        "required_nest",
        "required_nest_point",
        "required_clan",
        "required_clan_rank",
        "required_rank",
    }
)


class ItemCatalog:
    """Ids e vendas do catálogo em memória, carregados na primeira compra (LazyItemCatalog)."""

    def __init__(
        self,
        inventory_items: frozenset[int],
        morats: frozenset[int],
        sales: dict[int, SaleInfo],
    ) -> None:
        self._inventory_items = inventory_items
        self._morats = morats
        self._sales = sales

    @classmethod
    def open(cls, path: Path) -> ItemCatalog:
        if not path.is_file():
            raise ValueError(f"catálogo do cliente não encontrado: {path}")
        uri = f"{path.resolve().as_uri()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as conn:
            conn.text_factory = _decode
            # Item (grupo 3) e Item_Equip (grupo 2) vão para o inventário; Morats (grupo 1), não.
            items = _type_ids(conn, "item") | _type_ids(conn, "Item_Equip")
            morats = _type_ids(conn, "Morats")
            sales: dict[int, SaleInfo] = {}
            for table, prefix, is_morat in _SALE_TABLES:
                sales.update(_sale_infos(conn, table, prefix, is_morat))
        return cls(frozenset(items), frozenset(morats), sales)

    def is_inventory_item(self, catalog_id: int) -> bool:
        return catalog_id in self._inventory_items

    def is_morat(self, catalog_id: int) -> bool:
        return catalog_id in self._morats

    def sale(self, catalog_id: int) -> SaleInfo | None:
        return self._sales.get(catalog_id)


class LazyItemCatalog:
    """`ItemCatalog` aberto na primeira consulta, sem cache do erro. O canal sobe sem o cliente
    instalado; enquanto o wdb não abre, cada consulta levanta ValueError e a compra é recusada."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._loaded: ItemCatalog | None = None

    def _catalog(self) -> ItemCatalog:
        if self._loaded is None:
            self._loaded = ItemCatalog.open(self._path)
        return self._loaded

    def is_inventory_item(self, catalog_id: int) -> bool:
        return self._catalog().is_inventory_item(catalog_id)

    def is_morat(self, catalog_id: int) -> bool:
        return self._catalog().is_morat(catalog_id)

    def sale(self, catalog_id: int) -> SaleInfo | None:
        return self._catalog().sale(catalog_id)


def _decode(raw: bytes) -> str:
    return raw.decode("cp1252", errors="replace")


def _type_ids(conn: sqlite3.Connection, table: str) -> set[int]:
    # `table` é sempre uma constante deste módulo, nunca entrada externa.
    rows = conn.execute(f"SELECT DISTINCT type FROM {table} WHERE type IS NOT NULL")
    return {int(row[0]) for row in rows if str(row[0]).isdigit()}


def _sale_infos(
    conn: sqlite3.Connection, table: str, prefix: str, is_morat: bool
) -> dict[int, SaleInfo]:
    # `table` e `prefix` são constantes deste módulo, nunca entrada externa.
    rows = conn.execute(
        f'SELECT type, "key", value FROM {table} WHERE "key" LIKE ? OR "key" LIKE ?',
        (f"{prefix}buy%", f"{prefix}required%"),
    )
    campos: dict[int, dict[str, int]] = {}
    for tipo, chave, valor in rows:
        nome = str(chave).removeprefix(prefix)
        if not str(tipo).isdigit() or nome not in _SALE_NAMES:
            continue
        campos.setdefault(int(tipo), {})[nome] = int(valor)
    return {
        catalog_id: SaleInfo(
            is_morat=is_morat,
            ld=_quatro(nomes, "buy_point"),
            cash=_quatro(nomes, "buy_cash"),
            requirements=Requirements(
                level=nomes.get("required_level", 0),
                nest=nomes.get("required_nest", 0),
                nest_point=nomes.get("required_nest_point", 0),
                clan=nomes.get("required_clan", 0),
                clan_rank=nomes.get("required_clan_rank", 0),
                rank=nomes.get("required_rank", 0),
            ),
        )
        for catalog_id, nomes in campos.items()
    }


def _quatro(nomes: dict[str, int], base: str) -> tuple[int, int, int, int]:
    return (
        nomes.get(f"{base}[0]", 0),
        nomes.get(f"{base}[1]", 0),
        nomes.get(f"{base}[2]", 0),
        nomes.get(f"{base}[3]", 0),
    )
