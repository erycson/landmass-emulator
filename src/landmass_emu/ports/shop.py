"""Portas da loja: débito e criação da unidade numa transação só (`ShopRepository`), e a venda por
id do catálogo (`ShopItemRepository`, D191). A loja depende disto, nunca do SQLAlchemy."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from landmass_emu.domain.currency import Currency
from landmass_emu.domain.inventory import ItemUnit, MoratUnit


class ShopRepository(Protocol):
    async def purchase(
        self, account_id: int, currency: Currency, price: int, unit: ItemUnit | MoratUnit
    ) -> bool:
        """Debita `price` se o saldo cobre e grava `unit` na mesma transação. False = saldo
        insuficiente, e nada é gravado. Índice ou gate já ocupado levanta `InventoryConflict`, sem
        débito."""
        ...


@dataclass(frozen=True, slots=True)
class ShopItem:
    """Venda de um id do catálogo. `ld` é o `point` do banco; cada tupla tem o preço dos níveis
    0 a 3 (o prazo de item, ou nível 0 de morat)."""

    catalog_id: int
    name: str
    enabled: bool
    ld: tuple[int, int, int, int]
    cash: tuple[int, int, int, int]


class ShopItemRepository(Protocol):
    async def get(self, catalog_id: int) -> ShopItem | None: ...

    async def all_items(self) -> tuple[ShopItem, ...]:
        """Todas as vendas, na ordem do id do catálogo."""
        ...

    async def count(self) -> int: ...

    async def sync(self, items: Sequence[ShopItem]) -> tuple[int, int]:
        """Insere as vendas novas (com o `enabled` da linha) e atualiza nome e preços das
        existentes, sem mexer em `enabled`. Devolve (novas, atualizadas)."""
        ...

    async def set_enabled(self, catalog_id: int, enabled: bool) -> bool:
        """False se o id não está na tabela."""
        ...

    async def set_prices(
        self,
        catalog_id: int,
        ld: tuple[int, int, int, int],
        cash: tuple[int, int, int, int],
    ) -> bool:
        """False se o id não está na tabela."""
        ...
