"""Porta do uso de item especial (Item Surpresa e Adicionar Hangar): consumo, prêmio e gate numa
transação só. Quem chama já segura a trava da conta."""

from collections.abc import Sequence
from typing import Protocol

from landmass_emu.domain.inventory import ItemUnit


class UseRepository(Protocol):
    async def consume(
        self,
        account_id: int,
        index: int,
        catalog_id: int,
        *,
        ld: int,
        grants: Sequence[ItemUnit],
        gate_count: int | None,
    ) -> bool:
        """Apaga a unidade `index` (do `catalog_id`), credita `ld`, grava `grants` e, se
        `gate_count` não é None, troca a contagem de gates. False = a unidade não está mais na
        conta, e nada é gravado. Índice ocupado levanta `InventoryConflict`, sem gravar."""
        ...
