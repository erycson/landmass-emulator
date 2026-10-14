"""Equipar e desequipar (F6): slots, regras de requisito e o `EquipService` que as aplica.

Fontes: docs/architecture/07-progression.md §5.4 (R-USE-*); re/protocol_full.md §9 (slots, 560,
570 e respostas). O slot de peça vem do catálogo (`item_slot` de `Item_Equip`), nunca do cliente.
"""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Protocol

from landmass_emu.domain.inventory import ItemUnit, MoratUnit, utc_now
from landmass_emu.domain.locks import AccountLocks
from landmass_emu.domain.progression import Level, RankTable
from landmass_emu.domain.shop import Requirements, SaleInfo
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.equipment import EquipmentRepository
from landmass_emu.ports.inventory import InventoryRepository
from landmass_emu.ports.progression import ProgressionRepository

log = logging.getLogger(__name__)

# `LM_MORATS_INFO` (16 peças, `@0x34..0x53` do 103) na ordem do dump. O `item_slot` de `Item_Equip`
# (0 a 11) é o índice desta tabela. Verificado no wdb: 0 `MainWeapon`, 1 `SubWeapon`, 2 `Melee`,
# 3 a 5 `EtcWeapon`, 6 `Booster`, 7 `Generator`, 8 a 11 `Head`, `Body`, `Arm`, `Leg`.
# 5 e 12 a 15 não têm item no wdb (etc_item não é equipável por enquanto).
SLOT_NAMES: tuple[str, ...] = (
    "main_weapon",
    "sub_weapon",
    "melee_weapon",
    "etc_weapon_00",
    "etc_weapon_01",
    "etc_weapon_02",
    "booster",
    "generator",
    "head",
    "body",
    "arm",
    "leg",
    "etc_item_00",
    "etc_item_01",
    "etc_item_02",
    "etc_item_03",
)
# Skins do morat (`siSkinID[3]`, @0x64 de `LM_MORATS_INFO`): a pintura ocupa uma delas (D136).
# Fora de `SLOT_NAMES`: o `item_slot` das pinturas (13 a 25) não é índice de skin.
SKIN_SLOTS: tuple[str, ...] = ("skin_00", "skin_01", "skin_02")
PAINT_SKIN_SLOT = 0  # shortcut: a pintura entra em `skin_00`; `k` do 565 é fixo (inferido).
# `sEventSlot[10]` (LM_PLAYER_INFO) guarda o índice de inventário em 1 byte por slot.
SYSTEM_SLOT_COUNT = 10
SYSTEM_INDEX_MAX = 0xFE
GROUP_ITEM = 3
CLASS_SYSTEM = 8
CLASS_SKIN = 7


class UseResult(IntEnum):
    """Resultados de uso (561 e 571 têm mensagem pelo valor, em `NotifyItemUsed`).

    OK e NO_GATE seguem os casos do `switch` (-1, sem morat no gate). Os demais valores são
    genéricos e não têm mensagem própria no cliente: inferido, porque os `CERR_*` não têm valor no
    dump (D68). O -3 de skin (`CITEM_SKIN`) saiu: pintura agora se monta (D136)."""

    OK = 0
    NO_GATE = -1  # gate sem morat, ou morat de outra conta
    DENIED = -4  # genérico: índice inválido, vencido, slot cheio ou item fora do catálogo
    REQUIREMENT = -7  # classe, energia, força, agilidade, precisão, patente ou nest


class ItemRefusal(Exception):
    """Pedido recusado sem gravar nada. `result` é o código que vai na resposta."""

    def __init__(self, result: int, reason: str) -> None:
        super().__init__(reason)
        self.result = int(result)


@dataclass(frozen=True, slots=True)
class EquipSpec:
    """Requisitos de equipar de um item do grupo 2 (`Item_Equip`)."""

    slot: int  # `item_slot` 0 a 11
    class_mask: int  # `item_required_class`: um dígito decimal por classe (1, 10, 100, 1000)
    power: int  # energia (`item_required_power`)
    strength: int
    agility: int
    precision: int
    requirements: Requirements  # patente e nest (R-REQ-01), com a mesma regra da compra


@dataclass(frozen=True, slots=True)
class MoratStats:
    """Atributos do morat (`Morats` do wdb). `morat_class` é o `required_class` da espécie."""

    morat_class: int  # Assault 1, Sniper 10, Defender 100, Engineer 1000, Special 10000
    power: int
    strength: int
    agility: int
    precision: int


def slot_name(slot: int) -> str:
    return SLOT_NAMES[slot]


def slot_of(name: str) -> int | None:
    return SLOT_NAMES.index(name) if name in SLOT_NAMES else None


def group_and_class(catalog_id: int) -> tuple[int, int]:
    """Grupo e classe do id (R-CAT-01): grupo = id / 1e8, classe = (id / 1e6) % 100."""
    return catalog_id // 100_000_000, (catalog_id // 1_000_000) % 100


def is_system_item(catalog_id: int) -> bool:
    group, klass = group_and_class(catalog_id)
    return group == GROUP_ITEM and klass == CLASS_SYSTEM


def is_skin(catalog_id: int) -> bool:
    group, klass = group_and_class(catalog_id)
    return group == GROUP_ITEM and klass == CLASS_SKIN


def class_allows(class_mask: int, morat_class: int) -> bool:
    """Regra do cliente (`IsAvailableItem`, XInterface L19897): máscara 0 vale para todos; senão,
    o dígito da classe do morat na máscara decimal."""
    if morat_class <= 0:
        return False
    return class_mask == 0 or (class_mask // morat_class) % 10 > 0


def pieces_of(morat_id: int | None, items: Iterable[ItemUnit]) -> tuple[int, ...]:
    """Índices das peças montadas no morat, na ordem de `SLOT_NAMES`: -1 onde não há peça
    (o cliente usa o `DefaultSet` da espécie). Depois, as 3 skins: índice da pintura montada
    em `skin_00..02` (D136), 0 onde não há pintura."""
    pieces = [-1] * len(SLOT_NAMES)
    skins = [0] * len(SKIN_SLOTS)
    if morat_id is not None:
        for item in items:
            if item.account_morat_id != morat_id:
                continue
            if item.slot_name in SLOT_NAMES:
                pieces[SLOT_NAMES.index(item.slot_name or "")] = item.inventory_index
            elif item.slot_name in SKIN_SLOTS:
                skins[SKIN_SLOTS.index(item.slot_name or "")] = item.inventory_index
    return (*pieces, *skins)


class EquipCatalog(Protocol):
    def is_morat(self, catalog_id: int) -> bool: ...

    def is_inventory_item(self, catalog_id: int) -> bool: ...

    def equip_spec(self, catalog_id: int) -> EquipSpec | None: ...

    def morat_stats(self, catalog_id: int) -> MoratStats | None: ...

    def sale(self, catalog_id: int) -> SaleInfo | None: ...


class LevelSource(Protocol):
    """Só a tabela de patentes (`LevelList` do wdb). O teste pode dar outra."""

    def level_list(self) -> tuple[Level, ...]: ...


@dataclass(frozen=True, slots=True)
class Mounted:
    """Montagem gravada. Peça: `gate` e `slot` (0 a 11), resposta 562. Sistema: `slot` (0 a 9),
    resposta 554 com o registro do item. Pintura (`skin`): `slot` é o `k` da skin, resposta 565."""

    unit: ItemUnit
    gate: int | None
    slot: int
    system: bool
    skin: bool = False


@dataclass(frozen=True, slots=True)
class Unmounted:
    gate: int
    slot: int  # slot de peça (0 a 15), o mesmo de 572; `k` da skin quando `skin`
    skin: bool = False


class EquipService:
    """Equipar e desequipar peça e item de sistema. Valida o que o cliente não valida (D70): dono,
    prazo, gate, classe, atributos, patente e nest. Serializado pela trava da conta."""

    def __init__(
        self,
        *,
        catalog: EquipCatalog,
        levels: LevelSource,
        inventory: InventoryRepository,
        equipment: EquipmentRepository,
        accounts: AccountRepository,
        progression: ProgressionRepository,
        locks: AccountLocks | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._catalog = catalog
        self._levels = levels
        self._inventory = inventory
        self._equipment = equipment
        self._accounts = accounts
        self._progression = progression
        self._locks = locks or AccountLocks()
        self._clock = clock

    async def equip(self, account_id: int, index: int, gate: int) -> Mounted:
        async with self._locks.of(account_id):
            try:
                return await self._equip(account_id, index, gate)
            except ValueError as e:
                # Catálogo ausente ou dado inesperado: recusa sem gravar, e loga como erro.
                log.error("equipar %d no gate %d recusado: %s", index, gate, e)
                raise ItemRefusal(UseResult.DENIED, str(e)) from e

    async def unequip(self, account_id: int, index: int, gate: int) -> Unmounted:
        async with self._locks.of(account_id):
            return await self._unequip(account_id, index, gate)

    async def _equip(self, account_id: int, index: int, gate: int) -> Mounted:
        items = await self._inventory.items(account_id)
        unit = _find_item(items, index)
        if unit is None:
            raise ItemRefusal(UseResult.DENIED, f"índice {index} não é desta conta")
        if unit.expires_at is not None and unit.expires_at <= self._clock():
            raise ItemRefusal(UseResult.DENIED, f"índice {index} vencido: renovar antes")
        if is_system_item(unit.catalog_id):
            return await self._mount_system(account_id, unit, items)
        spec = self._catalog.equip_spec(unit.catalog_id)
        if spec is None and not is_skin(unit.catalog_id):
            raise ItemRefusal(UseResult.DENIED, f"{unit.catalog_id} não é equipamento de morat")
        morats = await self._inventory.morats(account_id)
        morat = _find_gate(morats, gate)
        if morat is None or morat.id is None:
            raise ItemRefusal(UseResult.NO_GATE, f"gate {gate} sem morat")
        if unit.account_morat_id is not None:
            raise ItemRefusal(UseResult.DENIED, f"índice {index} já está montado")
        if spec is None:
            # Pintura: ocupa `skin_00`; a que estava lá sai na mesma transação (D136).
            await self._equipment.mount(account_id, index, morat.id, SKIN_SLOTS[PAINT_SKIN_SLOT])
            return Mounted(unit=unit, gate=gate, slot=PAINT_SKIN_SLOT, system=False, skin=True)
        stats = self._catalog.morat_stats(morat.catalog_id)
        if stats is None:
            raise ItemRefusal(UseResult.DENIED, f"morat {morat.catalog_id} sem atributos")
        await self._check_requirements(account_id, spec, stats)
        name = slot_name(spec.slot)
        # Peça ocupada sai na mesma transação (o repositório), antes da nova entrar.
        await self._equipment.mount(account_id, index, morat.id, name)
        return Mounted(unit=unit, gate=gate, slot=spec.slot, system=False)

    async def _mount_system(
        self, account_id: int, unit: ItemUnit, items: list[ItemUnit]
    ) -> Mounted:
        if unit.system_slot is not None:
            raise ItemRefusal(UseResult.DENIED, f"índice {unit.inventory_index} já está ativo")
        if unit.inventory_index > SYSTEM_INDEX_MAX:
            # shortcut: sEventSlot guarda o índice em 1 byte; itens acima de 254 não cabem.
            raise ItemRefusal(UseResult.DENIED, "índice acima de 254 não cabe no sEventSlot")
        used = {item.system_slot for item in items if item.system_slot is not None}
        slot = next((s for s in range(SYSTEM_SLOT_COUNT) if s not in used), None)
        if slot is None:
            raise ItemRefusal(UseResult.DENIED, "sem slot de sistema livre")
        await self._equipment.set_system_slot(account_id, unit.inventory_index, slot)
        return Mounted(unit=unit, gate=None, slot=slot, system=True)

    async def _check_requirements(
        self, account_id: int, spec: EquipSpec, stats: MoratStats
    ) -> None:
        if not class_allows(spec.class_mask, stats.morat_class):
            raise ItemRefusal(UseResult.REQUIREMENT, "classe do morat não aceita o item")
        for need, have, name in (
            (spec.power, stats.power, "energia"),
            (spec.strength, stats.strength, "força"),
            (spec.agility, stats.agility, "agilidade"),
            (spec.precision, stats.precision, "precisão"),
        ):
            if need > have:
                raise ItemRefusal(UseResult.REQUIREMENT, f"{name} {have} abaixo de {need}")
        level = 0
        if spec.requirements.level:
            progress = await self._progression.get(account_id)
            level = RankTable(self._levels.level_list()).level_for(progress.total_exp).level
        nest = await self._accounts.regular_nest(account_id)
        missing = spec.requirements.unmet(level=level, nest=nest)
        if missing is not None:
            raise ItemRefusal(UseResult.REQUIREMENT, missing)

    async def _unequip(self, account_id: int, index: int, gate: int) -> Unmounted:
        items = await self._inventory.items(account_id)
        unit = _find_item(items, index)
        if unit is None:
            raise ItemRefusal(UseResult.DENIED, f"índice {index} não é desta conta")
        if unit.system_slot is not None:
            # shortcut: não há resposta que limpe o sEventSlot no cliente; o slot sai no relogin.
            raise ItemRefusal(UseResult.DENIED, "item de sistema não desmonta por este caminho")
        if unit.account_morat_id is None or unit.slot_name is None:
            raise ItemRefusal(UseResult.DENIED, f"índice {index} não está montado")
        morats = await self._inventory.morats(account_id)
        morat = next((m for m in morats if m.id == unit.account_morat_id), None)
        if morat is None or morat.gate_index != gate:
            raise ItemRefusal(UseResult.NO_GATE, f"índice {index} não está no gate {gate}")
        if unit.slot_name in SKIN_SLOTS:
            await self._equipment.unmount(account_id, index)
            return Unmounted(gate=gate, slot=SKIN_SLOTS.index(unit.slot_name), skin=True)
        slot = slot_of(unit.slot_name)
        if slot is None:
            raise ItemRefusal(UseResult.DENIED, f"slot {unit.slot_name} desconhecido")
        await self._equipment.unmount(account_id, index)
        return Unmounted(gate=gate, slot=slot)


def _find_item(items: Iterable[ItemUnit], index: int) -> ItemUnit | None:
    return next((item for item in items if item.inventory_index == index), None)


def _find_gate(morats: Iterable[MoratUnit], gate: int) -> MoratUnit | None:
    return next((morat for morat in morats if morat.gate_index == gate), None)
