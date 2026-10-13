"""Operações de inventário da CLI: item com prazo e morat em gate. Validação no domínio, gravação
pelo repositório. Conta é buscada pelo usuário (login); nada é criado implicitamente."""

from landmass_emu.domain.account import Account
from landmass_emu.domain.inventory import InventoryService, ItemUnit, MoratUnit
from landmass_emu.domain.starter_kit import StarterKit
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.inventory import InventoryRepository


async def _find_account(accounts: AccountRepository, username: str) -> Account:
    account = await accounts.find_by_username(username)
    if account is None:
        raise ValueError(f"conta {username!r} não existe")
    return account


class InventoryAdmin:
    def __init__(
        self,
        accounts: AccountRepository,
        inventory: InventoryRepository,
        service: InventoryService,
    ) -> None:
        self._accounts = accounts
        self._inventory = inventory
        self._service = service

    async def add_item(self, username: str, catalog_id: int, days: int) -> ItemUnit:
        account = await _find_account(self._accounts, username)
        used = [unit.inventory_index for unit in await self._inventory.items(account.id)]
        unit = self._service.new_item(account.id, catalog_id, days, used)
        await self._inventory.add_item(unit)
        return unit

    async def add_morat(self, username: str, catalog_id: int, gate: int) -> MoratUnit:
        account = await _find_account(self._accounts, username)
        morats = await self._inventory.morats(account.id)
        used = [m.gate_index for m in morats if m.gate_index is not None]
        unit = self._service.new_morat(account.id, catalog_id, gate, used)
        await self._inventory.add_morat(unit)
        return unit


class StarterKitAdmin:
    """Kit inicial: na criação (`account create`) e em conta existente (`account kit apply`).
    Gate ocupado é pulado, então aplicar de novo não duplica."""

    def __init__(
        self,
        accounts: AccountRepository,
        inventory: InventoryRepository,
        kit: StarterKit,
    ) -> None:
        self._accounts = accounts
        self._inventory = inventory
        self._kit = kit

    async def apply(self, username: str) -> int:
        account = await _find_account(self._accounts, username)
        morats = await self._inventory.morats(account.id)
        used = [m.gate_index for m in morats if m.gate_index is not None]
        units = self._kit.plan(account.id, used)
        for unit in units:
            await self._inventory.add_morat(unit)
        return len(units)
