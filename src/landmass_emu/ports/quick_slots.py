"""Porta dos atalhos da conta (`account_quick_slots`). Hoje só a semeadura: o cliente não tem opcode
de carga e de gravação (re/features.md §4), então nada lê estes dados no protocolo."""

from collections.abc import Sequence
from typing import Protocol

from landmass_emu.domain.quick_slots import QuickSlot


class QuickSlotRepository(Protocol):
    async def seed(self, account_id: int, slots: Sequence[QuickSlot]) -> int:
        """Grava os slots que a conta ainda não tem. Devolve quantos foram gravados."""
        ...

    async def slots(self, account_id: int) -> list[QuickSlot]: ...
