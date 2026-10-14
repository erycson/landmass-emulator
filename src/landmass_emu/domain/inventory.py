"""Inventário da conta: itens e morats, criação e prazo. Regras puras, sem IO.

Itens (grupos 2 e 3 do catálogo) e morats (grupo 1) têm índices em mapas separados no cliente
(`FUN_100236b0` e `FUN_100237d0`). O morat usa como índice o próprio gate: o cliente guarda o
morat em `sGate[k].siIdx` e busca por esse valor (`GetMoratsInfoByGate`, dump de LM_Engine).
Inferido: ver re/layouts_f0.md §8 e D30.
"""

import uuid
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import IntEnum

from landmass_emu.ports.catalog import Catalog

GATE_COUNT = 8
# Gates de início (inferido: o kit dá 4 morats; o Adicionar Hangar diz "até 8").
BASE_GATE_COUNT = 4
# 102 e 103 mandam o índice como u16 (`*(short*)param_2` no dispatcher).
MAX_INVENTORY_INDEX = 0xFFFF
# Índice 0 não resolve como peça no cliente (`GetItemInfoByID(0)` falha em GetWeaponInfo), então
# começamos em 1 (inferido). shortcut: revisar se o 102 aceitar 0 no cliente real.
FIRST_INVENTORY_INDEX = 1


class ApplyFlag(IntEnum):
    """`ITEM_APPLY` do cliente, pela ordem do enum (inferido). Hoje só REALTIME é criado."""

    UNLIMIT = 0
    SIZE = 1
    REALTIME = 2
    PLAYTIME = 3
    ENABLE = 4


def _wire_apply_value(flag: ApplyFlag, value: int | None, expires_at: datetime | None) -> int:
    """`iApplyValue` como o cliente lê. REALTIME: instante de fim em segundos Unix (inferido:
    o 102 do cliente chama `time()` antes de inserir). Sem prazo, 0."""
    if flag is ApplyFlag.REALTIME:
        return 0 if expires_at is None else int(expires_at.timestamp())
    return value or 0


@dataclass(frozen=True, slots=True)
class ItemUnit:
    account_id: int
    inventory_index: int
    catalog_id: int
    item_guid: str
    apply_flag: ApplyFlag
    apply_value: int | None
    expires_at: datetime | None
    # Montagem (F6): morat dono e slot de peça (`SLOT_NAMES`), ou slot de sistema (0 a 9).
    account_morat_id: int | None = None
    slot_name: str | None = None
    system_slot: int | None = None

    def wire_apply_value(self) -> int:
        return _wire_apply_value(self.apply_flag, self.apply_value, self.expires_at)


@dataclass(frozen=True, slots=True)
class MoratUnit:
    account_id: int
    inventory_index: int
    catalog_id: int
    item_guid: str
    gate_index: int | None
    apply_flag: ApplyFlag
    apply_value: int | None
    expires_at: datetime | None
    # Chave da linha em `account_morats`; None até gravar. Liga as peças montadas (F6).
    id: int | None = None

    def wire_apply_value(self) -> int:
        return _wire_apply_value(self.apply_flag, self.apply_value, self.expires_at)


def utc_now() -> datetime:
    return datetime.now(UTC)


def _new_guid() -> str:
    return str(uuid.uuid4())


class InventoryService:
    """Criação de item e morat com as validações que o cliente não faz (decisão do usuário)."""

    def __init__(
        self,
        catalog: Catalog,
        *,
        clock: Callable[[], datetime] = utc_now,
        new_guid: Callable[[], str] = _new_guid,
    ) -> None:
        self._catalog = catalog
        self._clock = clock
        self._new_guid = new_guid

    def is_morat(self, catalog_id: int) -> bool:
        return self._catalog.is_morat(catalog_id)

    def new_item(
        self, account_id: int, catalog_id: int, days: int, used_indexes: Collection[int]
    ) -> ItemUnit:
        if not self._catalog.is_inventory_item(catalog_id):
            raise ValueError(
                f"catálogo {catalog_id} não é item nem equipamento "
                "(morats entram por 'account morat add')"
            )
        if days < 1:
            raise ValueError(f"dias: mínimo 1, veio {days}")
        return ItemUnit(
            account_id=account_id,
            inventory_index=self._free_index(used_indexes),
            catalog_id=catalog_id,
            item_guid=self._new_guid(),
            apply_flag=ApplyFlag.REALTIME,
            apply_value=None,
            expires_at=self._clock() + timedelta(days=days),
        )

    def new_morat(
        self, account_id: int, catalog_id: int, gate: int, used_gates: Collection[int]
    ) -> MoratUnit:
        if not self._catalog.is_morat(catalog_id):
            raise ValueError(f"catálogo {catalog_id} não é morat")
        if not 0 <= gate < GATE_COUNT:
            raise ValueError(f"gate: de 0 a {GATE_COUNT - 1}, veio {gate}")
        if gate in used_gates:
            raise ValueError(f"gate {gate} já tem um morat")
        return MoratUnit(
            account_id=account_id,
            inventory_index=gate,
            catalog_id=catalog_id,
            item_guid=self._new_guid(),
            gate_index=gate,
            apply_flag=ApplyFlag.UNLIMIT,
            apply_value=None,
            expires_at=None,
        )

    @staticmethod
    def _free_index(used: Collection[int]) -> int:
        taken = set(used)
        index = FIRST_INVENTORY_INDEX
        while index in taken:
            index += 1
        if index > MAX_INVENTORY_INDEX:
            raise ValueError("inventário cheio: sem índice livre de 16 bits")
        return index


def enabled_gates(gate_count: int, morat_gates: Iterable[int]) -> tuple[int, ...]:
    """Gates com bEnable no 101: os da contagem da conta e os já ocupados por morat (R-GATE-01)."""
    top = max((gate + 1 for gate in morat_gates), default=0)
    return tuple(range(min(max(gate_count, top), GATE_COUNT)))
