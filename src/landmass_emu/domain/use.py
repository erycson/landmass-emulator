"""Uso de itens especiais no 560: Item Surpresa (gacha, 308010006) e Adicionar Hangar (308010005).

Qualquer outro índice devolve None e segue para o equipar (F6). Consumo e prêmio (ou gate novo) vão
numa transação só (D20), sob a trava da conta, como a compra e o equipar.
"""

import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from landmass_emu.domain.equipment import ItemRefusal, UseResult
from landmass_emu.domain.gacha import ItemNames, Prize, draw, prize_of
from landmass_emu.domain.inventory import GATE_COUNT, InventoryService, ItemUnit, utc_now
from landmass_emu.domain.locks import AccountLocks
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.inventory import InventoryConflict, InventoryRepository
from landmass_emu.ports.progression import ProgressionRepository
from landmass_emu.ports.use import UseRepository

log = logging.getLogger(__name__)

GACHA_ITEM = 308010006  # Item Surpresa
ADD_GATE_ITEM = 308010005  # Adicionar Hangar: +1 gate, até GATE_COUNT (wdb: "até 8 Hangar")


@dataclass(frozen=True, slots=True)
class GachaOpened:
    index: int  # índice do Item Surpresa consumido (chave do 591)
    prizes: tuple[Prize, ...]
    granted: tuple[ItemUnit, ...]  # itens novos no hangar (102 depois do 591)
    ld: int  # saldos depois do crédito
    cash: int


@dataclass(frozen=True, slots=True)
class GateAdded:
    index: int
    gate_count: int


class ItemUseService:
    def __init__(
        self,
        *,
        names: ItemNames,
        inventory: InventoryService,
        items: InventoryRepository,
        accounts: AccountRepository,
        progression: ProgressionRepository,
        repository: UseRepository,
        locks: AccountLocks | None = None,
        rng: random.Random | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._names = names
        self._inventory = inventory
        self._items = items
        self._accounts = accounts
        self._progression = progression
        self._repository = repository
        self._locks = locks or AccountLocks()
        self._rng = rng or random.Random()  # noqa: S311 - sorteio de jogo, não é segredo
        self._clock = clock

    async def use(self, account_id: int, index: int) -> GachaOpened | GateAdded | None:
        async with self._locks.of(account_id):
            items = await self._items.items(account_id)
            item = next((i for i in items if i.inventory_index == index), None)
            if item is None or item.account_morat_id is not None or item.system_slot is not None:
                return None  # inexistente, montado ou de sistema: o equipar decide
            if item.expires_at is not None and item.expires_at <= self._clock():
                return None  # vencido: o equipar recusa com DENIED, como aos demais itens
            if item.catalog_id == GACHA_ITEM:
                return await self._open_gacha(account_id, item, [i.inventory_index for i in items])
            if item.catalog_id == ADD_GATE_ITEM:
                return await self._add_gate(account_id, item)
            return None

    async def _open_gacha(self, account_id: int, item: ItemUnit, used: list[int]) -> GachaOpened:
        drops = draw(self._rng)
        granted: list[ItemUnit] = []
        for drop in drops:
            if drop.catalog_id == 0:
                continue
            try:
                unit = self._inventory.new_item(account_id, drop.catalog_id, drop.days, used)
            except ValueError as e:
                raise ItemRefusal(UseResult.DENIED, str(e)) from e
            used.append(unit.inventory_index)
            granted.append(unit)
        ld = sum(drop.ld for drop in drops)
        if not await self._consume(account_id, item, ld=ld, grants=granted, gate_count=None):
            raise ItemRefusal(UseResult.DENIED, "item já consumido")
        after = await self._progression.get(account_id)
        return GachaOpened(
            index=item.inventory_index,
            prizes=tuple(prize_of(drop, self._names) for drop in drops),
            granted=tuple(granted),
            ld=after.ld,
            cash=after.cash,
        )

    async def _add_gate(self, account_id: int, item: ItemUnit) -> GateAdded:
        current = await self._accounts.gate_count(account_id)
        if current >= GATE_COUNT:
            raise ItemRefusal(UseResult.GATE_LIMIT, f"hangar já tem {GATE_COUNT} gates")
        if not await self._consume(account_id, item, ld=0, grants=(), gate_count=current + 1):
            raise ItemRefusal(UseResult.DENIED, "item já consumido")
        return GateAdded(index=item.inventory_index, gate_count=current + 1)

    async def _consume(
        self,
        account_id: int,
        item: ItemUnit,
        *,
        ld: int,
        grants: tuple[ItemUnit, ...] | list[ItemUnit],
        gate_count: int | None,
    ) -> bool:
        try:
            return await self._repository.consume(
                account_id,
                item.inventory_index,
                item.catalog_id,
                ld=ld,
                grants=tuple(grants),
                gate_count=gate_count,
            )
        except InventoryConflict as e:
            log.error("uso de %d recusado: %s", item.inventory_index, e)
            return False
