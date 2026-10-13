"""Porta do catálogo estático (`landmass.wdb`, somente leitura). Domínio e CLI dependem disto."""

from typing import Protocol


class Catalog(Protocol):
    def is_inventory_item(self, catalog_id: int) -> bool: ...

    def is_morat(self, catalog_id: int) -> bool: ...
