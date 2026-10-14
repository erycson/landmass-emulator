"""Porta do consumo de item de sistema (D131 a D134). Uma transação: apaga a unidade e grava o
efeito na conta. Argumentos primitivos (o `effect` é `domain.consumables.Effect`) para não importar
o domínio daqui."""

from datetime import datetime
from typing import Protocol


class ConsumableRepository(Protocol):
    async def consume(
        self,
        account_id: int,
        inventory_index: int,
        catalog_id: int,
        effect: int,
        value: int,
        at: datetime,
    ) -> bool:
        """Apaga a unidade (conta, índice e id) e grava o efeito na conta, numa transação. False =
        a unidade não existe mais: nada foi gravado."""
        ...
