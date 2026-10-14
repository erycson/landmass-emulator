"""Consumíveis de sistema que somem ao usar: Queima de Arquivo, Reconstituir, Alistar e Troca de
Função (D131 a D134). Regras puras de efeito e o `ConsumableService` que as aplica numa transação.

Fonte: `item_desc` do `landmass.wdb` (classe 8, tipo 1 ONCE); 560 com `value` (LM_JoinNestPage e
LM_ChangeMainMoratsPage); respostas 568, 569 e 590 (`tools/re/protocol_full.md` §9). Os demais
itens de
sistema (buffs, Adicionar Hangar e Item Surpresa) não passam por aqui: `NotConsumable`.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum

from landmass_emu.domain.equipment import ItemRefusal, UseResult
from landmass_emu.domain.inventory import ItemUnit, utc_now
from landmass_emu.domain.locks import AccountLocks
from landmass_emu.domain.regular import MORAT_CLASS_RANGE, NEST_RANGE
from landmass_emu.ports.consumables import ConsumableRepository
from landmass_emu.ports.inventory import InventoryRepository

QUEIMA_DE_ARQUIVO = 308010001
RECONSTITUIR = 308010002
ALISTAR = 308010003
TROCA_DE_FUNCAO = 308010004


class Effect(IntEnum):
    RESET_RECORD = 1  # Queima de Arquivo: vitórias, derrotas e abandono (`record_reset_at`)
    RESET_COMBAT = 2  # Reconstituir: abates, mortes e headshots (`combat_reset_at`)
    NEST = 3  # Alistar: nest regular, `value` 1 a 3
    MORAT_CLASS = 4  # Troca de Função: classe do morat regular, `value` 1 a 4


EFFECTS: dict[int, Effect] = {
    QUEIMA_DE_ARQUIVO: Effect.RESET_RECORD,
    RECONSTITUIR: Effect.RESET_COMBAT,
    ALISTAR: Effect.NEST,
    TROCA_DE_FUNCAO: Effect.MORAT_CLASS,
}
# Efeitos que recebem valor (560 com `value` ≠ 0). Os de reset não recebem.
VALUE_EFFECTS = frozenset({Effect.NEST, Effect.MORAT_CLASS})


class NotConsumable(Exception):
    """O item não é um consumível deste serviço: o caminho antigo (F6) decide."""


@dataclass(frozen=True, slots=True)
class Consumed:
    """Consumo aprovado: a unidade (antes de apagar), o efeito, o valor (nest ou classe; 0 nos
    resets) e o instante gravado."""

    unit: ItemUnit
    effect: Effect
    value: int
    at: datetime


def _find(items: list[ItemUnit], index: int) -> ItemUnit | None:
    return next((item for item in items if item.inventory_index == index), None)


def check_value(effect: Effect, value: int) -> None:
    """Valor do 560: obrigatório em Alistar e Troca de Função (faixa do morat regular), proibido
    nos resets. Levanta `ItemRefusal` com -4."""
    if effect is Effect.NEST and value not in NEST_RANGE:
        raise ItemRefusal(UseResult.DENIED, f"nest {value} fora de 1 a 3")
    if effect is Effect.MORAT_CLASS and value not in MORAT_CLASS_RANGE:
        raise ItemRefusal(UseResult.DENIED, f"classe {value} fora de 1 a 4")
    if effect not in VALUE_EFFECTS and value != 0:
        raise ItemRefusal(UseResult.DENIED, f"{effect.name} não recebe valor")


class ConsumableService:
    """Usa um consumível: valida dono, prazo, efeito e valor, e consome (apaga a unidade) junto com
    a gravação do efeito. Serializado pela trava da conta (D72)."""

    def __init__(
        self,
        *,
        inventory: InventoryRepository,
        repository: ConsumableRepository,
        locks: AccountLocks | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._inventory = inventory
        self._repository = repository
        self._locks = locks or AccountLocks()
        self._clock = clock

    def handles(self, catalog_id: int) -> bool:
        return catalog_id in EFFECTS

    async def use(self, account_id: int, index: int, value: int) -> Consumed:
        """`NotConsumable` se o item não é deste serviço. `ItemRefusal` se a regra recusa."""
        async with self._locks.of(account_id):
            unit = _find(await self._inventory.items(account_id), index)
            if unit is None:
                raise ItemRefusal(UseResult.DENIED, f"índice {index} não é desta conta")
            effect = EFFECTS.get(unit.catalog_id)
            if effect is None:
                raise NotConsumable(unit.catalog_id)
            now = self._clock()
            if unit.expires_at is not None and unit.expires_at <= now:
                raise ItemRefusal(UseResult.DENIED, f"índice {index} vencido: renovar antes")
            check_value(effect, value)
            if not await self._repository.consume(
                account_id, index, unit.catalog_id, int(effect), value, now
            ):
                raise ItemRefusal(UseResult.DENIED, f"índice {index} já foi consumido")
            return Consumed(unit=unit, effect=effect, value=value, at=now)
