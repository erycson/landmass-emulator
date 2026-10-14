"""Porta da compra: débito e criação da unidade numa transação só. A loja depende disto."""

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
