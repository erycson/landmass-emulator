"""Catálogo do cliente: `landmass.wdb` (SQLite), só leitura. Implementa `Catalog`, `SaleCatalog` e
`EquipCatalog`.

Formato EAV: a coluna `type` de `item`, `Item_Equip` e `Morats` é o id do catálogo, e `key` é o nome
do campo (preço `buy_point[i]`/`buy_cash[i]`, requisito `required_*`, com prefixo `item_` nas
tabelas de item). Só essas chaves são lidas: `value` tem texto fora de UTF-8 em outras linhas.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

from landmass_emu.domain.equipment import SLOT_NAMES, EquipSpec, MoratStats
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
# Atributos de equipar (`Item_Equip`) e de morat (`Morats`), sem prefixo. `slot` é o `item_slot`.
_EQUIP_NAMES = (
    "slot",
    "required_class",
    "required_power",
    "required_strength",
    "required_agility",
    "required_precision",
)
_MORAT_NAMES = ("required_class", "power", "strength", "agility", "precision")


class ItemCatalog:
    """Ids, vendas e atributos de equipar do catálogo em memória (LazyItemCatalog o carrega)."""

    def __init__(
        self,
        inventory_items: frozenset[int],
        morats: frozenset[int],
        sales: dict[int, SaleInfo],
        equip: dict[int, EquipSpec],
        morat_stats: dict[int, MoratStats],
        names: dict[int, str] | None = None,
        defaults: dict[int, dict[str, int]] | None = None,
    ) -> None:
        self._inventory_items = inventory_items
        self._morats = morats
        self._sales = sales
        self._equip = equip
        self._morat_stats = morat_stats
        self._names = names or {}
        self._defaults = defaults or {}

    @classmethod
    def open(cls, path: Path) -> ItemCatalog:
        if not path.is_file():
            raise ValueError(f"catálogo do cliente não encontrado: {path}")
        uri = f"{path.resolve().as_uri()}?mode=ro"
        try:
            with closing(sqlite3.connect(uri, uri=True)) as conn:
                conn.text_factory = _decode
                # Item (grupo 3) e Item_Equip (grupo 2) vão ao inventário; Morats (grupo 1), não.
                items = _type_ids(conn, "item") | _type_ids(conn, "Item_Equip")
                morats = _type_ids(conn, "Morats")
                sales: dict[int, SaleInfo] = {}
                for table, prefix, is_morat in _SALE_TABLES:
                    sales.update(_sale_infos(conn, table, prefix, is_morat))
                equip_fields = _attributes(conn, "Item_Equip", "item_", _EQUIP_NAMES)
                morat_fields = _attributes(conn, "Morats", "", _MORAT_NAMES)
                names = _names(conn)
                defaults = _default_sets(conn)
        except sqlite3.Error as e:
            # Mesmo tratamento do `WdbCatalog`: quem consulta recebe ValueError, não erro do SQLite.
            raise ValueError(f"catálogo do cliente ilegível: {e}") from e
        # Equipar não depende de venda: um equipamento sem preço ainda monta.
        equip = {
            cid: _equip_spec(fields, sales[cid].requirements if cid in sales else Requirements())
            for cid, fields in equip_fields.items()
            if 0 <= fields.get("slot", -1) < len(SLOT_NAMES)
        }
        stats = {
            cid: _morat_stats(fields)
            for cid, fields in morat_fields.items()
            if "required_class" in fields
        }
        return cls(frozenset(items), frozenset(morats), sales, equip, stats, names, defaults)

    def is_inventory_item(self, catalog_id: int) -> bool:
        return catalog_id in self._inventory_items

    def is_morat(self, catalog_id: int) -> bool:
        return catalog_id in self._morats

    def sale(self, catalog_id: int) -> SaleInfo | None:
        return self._sales.get(catalog_id)

    def equip_spec(self, catalog_id: int) -> EquipSpec | None:
        return self._equip.get(catalog_id)

    def morat_stats(self, catalog_id: int) -> MoratStats | None:
        return self._morat_stats.get(catalog_id)

    def name(self, catalog_id: int) -> str | None:
        return self._names.get(catalog_id)

    def default_set(self, morat_id: int) -> dict[str, int]:
        """Peças padrão da espécie (chaves do `DefaultSet`: `MainWeapon`, `Skin1`...). Vazio se o
        morat não tem set no wdb."""
        return self._defaults.get(morat_id, {})


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

    def equip_spec(self, catalog_id: int) -> EquipSpec | None:
        return self._catalog().equip_spec(catalog_id)

    def morat_stats(self, catalog_id: int) -> MoratStats | None:
        return self._catalog().morat_stats(catalog_id)

    def name(self, catalog_id: int) -> str | None:
        return self._catalog().name(catalog_id)

    def default_set(self, morat_id: int) -> dict[str, int]:
        return self._catalog().default_set(morat_id)


def _decode(raw: bytes) -> str:
    return raw.decode("cp1252", errors="replace")


def _default_sets(conn: sqlite3.Connection) -> dict[int, dict[str, int]]:
    """Peças padrão por morat. `Morats.defaultset` aponta o set; `DefaultSet` traz as peças de cada
    set (`type` é o set, `key` a peça, `value` o id, vazio vira 0). Sem a tabela: sem padrões."""
    try:
        linhas = conn.execute('SELECT type, "key", value FROM DefaultSet').fetchall()
    except sqlite3.OperationalError:
        return {}
    sets: dict[str, dict[str, int]] = {}
    for tipo, chave, valor in linhas:
        sets.setdefault(str(tipo), {})[str(chave)] = _valor_inteiro(valor)
    padroes: dict[int, dict[str, int]] = {}
    for tipo, set_id in conn.execute(
        'SELECT type, value FROM Morats WHERE "key" = ?', ("defaultset",)
    ):
        if str(tipo).isdigit() and str(set_id) in sets:
            padroes[int(tipo)] = sets[str(set_id)]
    return padroes


def _valor_inteiro(valor: object) -> int:
    texto = str(valor or "").strip()
    return int(texto) if texto.isdigit() else 0


def _names(conn: sqlite3.Connection) -> dict[int, str]:
    """Nome exibido: `item_name` (item e Item_Equip) e `alias` (Morats), linhas `localize`."""
    names: dict[int, str] = {}
    for table, key in (("item", "item_name"), ("Item_Equip", "item_name"), ("Morats", "alias")):
        # `table` e `key` são constantes deste módulo.
        for tipo, valor in conn.execute(f'SELECT type, value FROM {table} WHERE "key" = ?', (key,)):
            if str(tipo).isdigit() and valor:
                names[int(tipo)] = str(valor)
    return names


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


def _attributes(
    conn: sqlite3.Connection, table: str, prefix: str, names: tuple[str, ...]
) -> dict[int, dict[str, int]]:
    # `table`, `prefix` e `names` são constantes deste módulo: só as chaves listadas são lidas.
    keys = [f"{prefix}{name}" for name in names]
    marks = ",".join("?" * len(keys))
    rows = conn.execute(f'SELECT type, "key", value FROM {table} WHERE "key" IN ({marks})', keys)
    campos: dict[int, dict[str, int]] = {}
    for tipo, chave, valor in rows:
        if str(tipo).isdigit() and str(valor).lstrip("-").isdigit():
            nome = str(chave).removeprefix(prefix)
            campos.setdefault(int(tipo), {})[nome] = int(valor)
    return campos


def _equip_spec(fields: dict[str, int], requirements: Requirements) -> EquipSpec:
    return EquipSpec(
        slot=fields["slot"],
        class_mask=fields.get("required_class", 0),
        power=fields.get("required_power", 0),
        strength=fields.get("required_strength", 0),
        agility=fields.get("required_agility", 0),
        precision=fields.get("required_precision", 0),
        requirements=requirements,
    )


def _morat_stats(fields: dict[str, int]) -> MoratStats:
    return MoratStats(
        morat_class=fields["required_class"],
        power=fields.get("power", 0),
        strength=fields.get("strength", 0),
        agility=fields.get("agility", 0),
        precision=fields.get("precision", 0),
    )


def _quatro(nomes: dict[str, int], base: str) -> tuple[int, int, int, int]:
    return (
        nomes.get(f"{base}[0]", 0),
        nomes.get(f"{base}[1]", 0),
        nomes.get(f"{base}[2]", 0),
        nomes.get(f"{base}[3]", 0),
    )
