"""Entrada no canal (100) com o inventário do login: 101 com nest, gates e slots de sistema, 111 (do
EntryHandlers), depois um 102 por item, um 103 por morat com gate (com as peças montadas) e um 585
por item vencido. Ordem de re/NOTES.md: 101 → 111 → 103×n; 102 antes de 103 é inferido."""

import dataclasses
from collections.abc import Sequence

from landmass_emu.domain.equipment import SYSTEM_SLOT_COUNT, pieces_of
from landmass_emu.domain.inventory import ItemUnit, MoratUnit, utc_now
from landmass_emu.handlers.channel.entry import EntryHandlers
from landmass_emu.net.server import Reply
from landmass_emu.net.session import Session
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.inventory import InventoryRepository
from landmass_emu.protocol.channel import CsInChannelServerOut
from landmass_emu.protocol.equipment import CsItemEndtimeOut
from landmass_emu.protocol.inventory import DEFAULT_PARTS, CsGetItemOut, CsGetMoratsOut


class LoginHandlers:
    """Envolve `EntryHandlers.in_channel_server` e acrescenta o inventário na mesma resposta."""

    def __init__(
        self,
        entry: EntryHandlers,
        accounts: AccountRepository,
        inventory: InventoryRepository,
    ) -> None:
        self._entry = entry
        self._accounts = accounts
        self._inventory = inventory

    async def in_channel_server(self, session: Session, payload: bytes) -> Sequence[Reply]:
        replies = list(await self._entry.in_channel_server(session, payload))
        account = session.account
        first = replies[0] if replies else None
        if account is None or not isinstance(first, CsInChannelServerOut):
            return replies
        items = await self._inventory.items(account.id)
        morats = await self._inventory.morats(account.id)
        # shortcut: morat sem gate não entra no login; o cliente não tem chave para ele fora de
        # sGate. Revisar quando a F6 ou a compra criar morat fora do gate.
        placed = [(morat, gate) for morat in morats if (gate := morat.gate_index) is not None]
        gates = tuple(gate for _, gate in placed)
        nest = await self._accounts.regular_nest(account.id)
        progress = dataclasses.replace(
            first.progress,
            nest=nest,
            morat_gates=gates,
            system_slots=_system_slots(items),
        )
        return [
            dataclasses.replace(first, progress=progress),
            *replies[1:],
            *(item_record(item) for item in items),
            *(morat_record(morat, pieces_of(morat.id, items)) for morat, _ in placed),
            *(CsItemEndtimeOut(item.inventory_index) for item in _expired(items)),
        ]


def item_record(unit: ItemUnit) -> CsGetItemOut:
    """Registro 102 de uma unidade do inventário. A loja manda o mesmo registro depois da compra."""
    return CsGetItemOut(
        inventory_index=unit.inventory_index,
        catalog_id=unit.catalog_id,
        item_guid=unit.item_guid,
        apply_flag=int(unit.apply_flag),
        apply_value=unit.wire_apply_value(),
    )


def morat_record(unit: MoratUnit, parts: tuple[int, ...] = DEFAULT_PARTS) -> CsGetMoratsOut:
    """Registro 103 de um morat, com as peças montadas (`pieces_of`). Sem gate não há chave no
    cliente (`sGate`), logo não há 103."""
    if unit.gate_index is None:
        raise ValueError(f"morat {unit.item_guid} sem gate: não tem registro 103")
    return CsGetMoratsOut(
        gate_index=unit.gate_index,
        catalog_id=unit.catalog_id,
        item_guid=unit.item_guid,
        apply_flag=int(unit.apply_flag),
        apply_value=unit.wire_apply_value(),
        parts=parts,
    )


def _system_slots(items: Sequence[ItemUnit]) -> tuple[int | None, ...]:
    """Índice do item de sistema em cada slot (`sEventSlot`); None = slot livre."""
    slots: list[int | None] = [None] * SYSTEM_SLOT_COUNT
    for item in items:
        if item.system_slot is not None:
            slots[item.system_slot] = item.inventory_index
    return tuple(slots)


def _expired(items: Sequence[ItemUnit]) -> list[ItemUnit]:
    now = utc_now()
    return [item for item in items if item.expires_at is not None and item.expires_at <= now]
