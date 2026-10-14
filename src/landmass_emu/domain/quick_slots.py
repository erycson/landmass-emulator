"""Atalhos da conta: os 5 slots que `InitializeQuickSlot` do SQL antigo (LM_account.sql) grava na
criação. O cliente não tem opcode de carga nem de gravação (re/features.md §4), então o conteúdo só
é gravado; nada o lê no protocolo ainda (D73)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QuickSlot:
    slot_index: int  # 0 a 4
    enabled: bool
    memo: str
    gate_index: int  # -1 = sem gate


# (slot, enable, memo, gate) de `InitializeQuickSlot`, na ordem do SQL antigo.
DEFAULT_QUICK_SLOTS: tuple[QuickSlot, ...] = (
    QuickSlot(0, True, "", 0),
    QuickSlot(1, True, "", 1),
    QuickSlot(2, False, "", 2),
    QuickSlot(3, False, "", 3),
    QuickSlot(4, False, "", -1),
)
