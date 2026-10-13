"""Entrada no canal (100) com o inventário do login: 101 com nest e gates, 111 (do EntryHandlers),
depois um 102 por item e um 103 por morat com gate. Ordem de re/NOTES.md: 101 → 111 → 103×n;
102 antes de 103 é inferido."""

import dataclasses
from collections.abc import Sequence

from landmass_emu.domain.inventory import ItemUnit, MoratUnit
from landmass_emu.handlers.channel.entry import EntryHandlers
from landmass_emu.net.server import Reply
from landmass_emu.net.session import Session
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.inventory import InventoryRepository
from landmass_emu.protocol.channel import CsInChannelServerOut
from landmass_emu.protocol.inventory import CsGetItemOut, CsGetMoratsOut


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
        return [
            dataclasses.replace(
                first,
                progress=dataclasses.replace(first.progress, nest=nest, morat_gates=gates),
            ),
            *replies[1:],
            *(_item_record(item) for item in items),
            *(_morat_record(morat, gate) for morat, gate in placed),
        ]


def _item_record(unit: ItemUnit) -> CsGetItemOut:
    return CsGetItemOut(
        inventory_index=unit.inventory_index,
        catalog_id=unit.catalog_id,
        item_guid=unit.item_guid,
        apply_flag=int(unit.apply_flag),
        apply_value=unit.wire_apply_value(),
    )


def _morat_record(unit: MoratUnit, gate: int) -> CsGetMoratsOut:
    return CsGetMoratsOut(
        gate_index=gate,
        catalog_id=unit.catalog_id,
        item_guid=unit.item_guid,
        apply_flag=int(unit.apply_flag),
        apply_value=unit.wire_apply_value(),
    )
