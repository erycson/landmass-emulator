"""Destruir e estender (F7): dono, morat e prazo, com os serviços que os aplicam.

Fontes: docs/architecture/07-progression.md §5.5 (R-DEST-*, R-EXT-*) e tools/re/protocol_full.md §9
(555, 556, 557, 559, 580 e respostas). Preço e prazo de extensão são os da compra (`quote`).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from landmass_emu.domain.currency import Currency
from landmass_emu.domain.equipment import ItemRefusal, UseResult
from landmass_emu.domain.inventory import ItemUnit, MoratUnit, utc_now
from landmass_emu.domain.locks import AccountLocks
from landmass_emu.domain.shop import BuyResult, SaleCatalog, quote
from landmass_emu.ports.equipment import EquipmentRepository
from landmass_emu.ports.inventory import InventoryRepository
from landmass_emu.ports.progression import ProgressionRepository


@dataclass(frozen=True, slots=True)
class Destroyed:
    """Resultado de 555. `gate` é o gate apagado (morat) ou o gate de onde o item saiu (R-DEST-01).
    `system_slot` manda 559 em vez de 556 para item de sistema."""

    index: int
    morat: bool
    gate: int | None
    system_slot: int | None
    # Unidade como estava antes do DELETE, para o log de economia.
    unit: ItemUnit | MoratUnit | None = field(default=None, compare=False)


@dataclass(frozen=True, slots=True)
class Extended:
    """Resultado de 580 com sucesso: novo prazo e saldos, que o 582 leva ao cliente."""

    index: int
    expires_at: datetime
    cash: int  # saldos depois do débito
    ld: int
    currency: Currency = field(default=Currency.LD, compare=False)
    price: int = field(default=0, compare=False)
    days: int = field(default=0, compare=False)
    previous_expires_at: datetime | None = field(default=None, compare=False)


def _find_unit(units: list[ItemUnit], index: int, catalog_id: int) -> ItemUnit:
    unit = next(
        (u for u in units if u.inventory_index == index and u.catalog_id == catalog_id), None
    )
    if unit is None:
        raise ItemRefusal(UseResult.DENIED, f"índice {index} com id {catalog_id} não existe")
    return unit


class DestroyService:
    """Destrói item ou morat. O destino é decidido pelo dono e pelo `catalog_id` gravado, então não
    depende do wdb. O último morat da conta não sai: sem morat a sala trava (dúvida 24)."""

    def __init__(
        self,
        *,
        inventory: InventoryRepository,
        equipment: EquipmentRepository,
        locks: AccountLocks | None = None,
    ) -> None:
        self._inventory = inventory
        self._equipment = equipment
        self._locks = locks or AccountLocks()

    async def destroy(self, account_id: int, catalog_id: int, index: int) -> Destroyed:
        async with self._locks.of(account_id):
            morats = await self._inventory.morats(account_id)
            morat = next(
                (m for m in morats if m.gate_index == index and m.catalog_id == catalog_id), None
            )
            if morat is not None:
                return await self._destroy_morat(account_id, morat, len(morats))
            return await self._destroy_item(account_id, catalog_id, index, morats)

    async def _destroy_morat(self, account_id: int, morat: MoratUnit, count: int) -> Destroyed:
        if count <= 1:
            raise ItemRefusal(UseResult.DENIED, "último morat da conta: a sala trava sem morat")
        if morat.id is None or morat.gate_index is None:
            raise ItemRefusal(UseResult.DENIED, "morat sem registro")
        await self._equipment.destroy_morat(account_id, morat.id)
        return Destroyed(
            index=morat.gate_index, morat=True, gate=morat.gate_index, system_slot=None, unit=morat
        )

    async def _destroy_item(
        self, account_id: int, catalog_id: int, index: int, morats: list[MoratUnit]
    ) -> Destroyed:
        items = await self._inventory.items(account_id)
        unit = _find_unit(items, index, catalog_id)
        gate: int | None = None
        if unit.account_morat_id is not None:
            owner = next((m for m in morats if m.id == unit.account_morat_id), None)
            gate = owner.gate_index if owner is not None else None
        await self._equipment.destroy_item(account_id, index)
        return Destroyed(
            index=index, morat=False, gate=gate, system_slot=unit.system_slot, unit=unit
        )


class ExtendService:
    """Estende o prazo de um item pela tabela da compra (R-EXT-01): soma a partir do prazo atual se
    ele ainda vale, senão a partir de agora. Morat não tem prazo: recusa."""

    def __init__(
        self,
        *,
        catalog: SaleCatalog,
        inventory: InventoryRepository,
        equipment: EquipmentRepository,
        progression: ProgressionRepository,
        locks: AccountLocks | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._catalog = catalog
        self._inventory = inventory
        self._equipment = equipment
        self._progression = progression
        self._locks = locks or AccountLocks()
        self._clock = clock

    async def extend(
        self, account_id: int, catalog_id: int, index: int, currency: Currency, option: int
    ) -> Extended:
        async with self._locks.of(account_id):
            morats = await self._inventory.morats(account_id)
            if any(m.gate_index == index and m.catalog_id == catalog_id for m in morats):
                raise ItemRefusal(UseResult.DENIED, "morat não tem prazo")
            unit = _find_unit(await self._inventory.items(account_id), index, catalog_id)
            sale = self._catalog.sale(catalog_id)
            if sale is None:
                raise ItemRefusal(UseResult.DENIED, f"{catalog_id} fora do catálogo")
            offer = quote(sale, currency, option)
            if offer.price <= 0 or offer.days <= 0:
                raise ItemRefusal(UseResult.DENIED, f"{catalog_id} sem prazo na opção {option}")
            now = self._clock()
            base = unit.expires_at if unit.expires_at is not None and unit.expires_at > now else now
            expires_at = base + timedelta(days=offer.days)
            if not await self._equipment.extend(
                account_id, currency, offer.price, index, expires_at
            ):
                shortage = (
                    BuyResult.LD_SHORTAGE if currency is Currency.LD else BuyResult.CASH_SHORTAGE
                )
                raise ItemRefusal(shortage, f"saldo abaixo de {offer.price}")
            after = await self._progression.get(account_id)
            return Extended(
                index=index,
                expires_at=expires_at,
                cash=after.cash,
                ld=after.ld,
                currency=currency,
                price=offer.price,
                days=offer.days,
                previous_expires_at=unit.expires_at,
            )
