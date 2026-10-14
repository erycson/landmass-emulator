"""Buffs ativos da conta (D137): Aumento de EXP, Aumento de LD e Ressurreição.

Um buff está ativo quando é um item de sistema de tipo BUFF (classe 8, tipo 2 no id), está
montado num slot de sistema (`sEventSlot`) e o prazo não venceu. Consumidos (ONCE) não contam.
O efeito de EXP e LD é aplicado pela recompensa de partida (R-REW-08, ×1.5); Ressurreição só
informa, porque o tempo de respawn é do servidor de partida, fora do canal.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime

from landmass_emu.domain.inventory import ItemUnit, utc_now
from landmass_emu.ports.inventory import InventoryRepository

AUMENTO_DE_EXP = 308020001
AUMENTO_DE_LD = 308020002
RESSURREICAO = 308020003
BUFF_IDS = frozenset({AUMENTO_DE_EXP, AUMENTO_DE_LD, RESSURREICAO})


@dataclass(frozen=True, slots=True)
class ActiveBuffs:
    exp: bool = False  # EXP × 1.5 na recompensa de partida
    ld: bool = False  # LD × 1.5 na recompensa de partida
    respawn: bool = False  # respawn em 7 s: aplicado pelo servidor de partida


def active_buffs(items: Iterable[ItemUnit], now: datetime) -> ActiveBuffs:
    """Buffs montados e não vencidos. Função pura, para a recompensa e para os testes."""
    ativos = {
        item.catalog_id
        for item in items
        if item.system_slot is not None
        and item.catalog_id in BUFF_IDS
        and (item.expires_at is None or item.expires_at > now)
    }
    return ActiveBuffs(
        exp=AUMENTO_DE_EXP in ativos,
        ld=AUMENTO_DE_LD in ativos,
        respawn=RESSURREICAO in ativos,
    )


class BuffService:
    """Consulta de buffs da conta, para a recompensa de partida (`active_buffs(account_id)`)."""

    def __init__(
        self,
        inventory: InventoryRepository,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._inventory = inventory
        self._clock = clock

    async def active_buffs(self, account_id: int) -> ActiveBuffs:
        return active_buffs(await self._inventory.items(account_id), self._clock())
