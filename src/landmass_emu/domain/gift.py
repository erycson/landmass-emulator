"""Presente e Depósito (F10): envio por nick (615, 616), listagem (610, 611) e resgate
(612, 613). Validação aqui; saldo e gravação ficam na porta `GiftRepository`.

Fonte: docs/architecture/07-progression.md §5.6 (R-GIFT-01 a 05) e re/protocol_full.md §3.
Presente não tem exigência de patente: `LevelList` tem `enable_gift` no nível 0 e exp -1 (dúvida 3).
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from landmass_emu.domain.currency import Currency
from landmass_emu.domain.inventory import InventoryService, ItemUnit
from landmass_emu.domain.locks import AccountLocks
from landmass_emu.domain.shop import SaleCatalog, quote
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.inventory import InventoryConflict, InventoryRepository
from landmass_emu.ports.progression import ProgressionRepository

if TYPE_CHECKING:
    from landmass_emu.ports.gifts import GiftRepository

log = logging.getLogger(__name__)

# Página do Depósito: 12 registros (SupplyInvenListPanel, 12 slots).
GIFT_PAGE_SIZE = 12
# `CERR_NOT_NICKNAME` (layouts_f0 §7.3): nick inexistente. -4055 e -4056 têm mensagem de saldo.
CERR_NOT_NICKNAME = -2407
CERR_BUY_CASH_SHORTAGE = -4055
CERR_BUY_POINT_SHORTAGE = -4056
# Recusa sem mensagem própria: o `switch` de NotifyItemGift cai no `default` (233000500).
SILENT = 8000


@dataclass(frozen=True, slots=True)
class Gift:
    """Linha de `gifts`. `sender_account_id` é o remetente; a compra não passa por aqui (hangar)."""

    id: int
    sender_account_id: int | None
    receiver_account_id: int
    slot: int  # chave u16 que o cliente devolve no 612 (única entre os pendentes da conta)
    catalog_id: int
    duration_days: int


class GiftRefusal(Exception):
    """Pedido recusado sem gravar nada. `result` é o código que vai na resposta."""

    def __init__(self, result: int, reason: str) -> None:
        super().__init__(reason)
        self.result = int(result)


@dataclass(frozen=True, slots=True)
class GiftSent:
    receiver_id: int
    price: int
    days: int
    cash: int  # saldos do remetente depois do débito
    ld: int


@dataclass(frozen=True, slots=True)
class GiftPage:
    page: int  # 0 a n, como o cliente pede
    gifts: tuple[Gift, ...]


def _shortage(currency: Currency) -> int:
    return CERR_BUY_POINT_SHORTAGE if currency is Currency.LD else CERR_BUY_CASH_SHORTAGE


class GiftService:
    """Presente, listagem e resgate. Envio trava remetente e destinatário em ordem de id (sem
    impasse); resgate trava só a conta que resgata. Mesma trava por conta da loja (D72)."""

    def __init__(
        self,
        *,
        catalog: SaleCatalog,
        inventory: InventoryService,
        items: InventoryRepository,
        accounts: AccountRepository,
        progression: ProgressionRepository,
        repository: GiftRepository,
        locks: AccountLocks | None = None,
    ) -> None:
        self._catalog = catalog
        self._inventory = inventory
        self._items = items
        self._accounts = accounts
        self._progression = progression
        self._repository = repository
        self._locks = locks or AccountLocks()

    async def send(
        self, sender_id: int, nick: str, catalog_id: int, currency: Currency, option: int
    ) -> GiftSent:
        receiver = await self._accounts.find_by_nickname(nick) if nick else None
        if receiver is None:
            raise GiftRefusal(CERR_NOT_NICKNAME, f"nick {nick!r} inexistente")
        if receiver.id == sender_id:
            raise GiftRefusal(SILENT, "presente para a própria conta")
        try:
            sale = self._catalog.sale(catalog_id)
        except ValueError as e:  # wdb ausente ou dado inesperado: recusa sem gravar
            log.error("presente de %d recusado: %s", catalog_id, e)
            raise GiftRefusal(SILENT, str(e)) from e
        if sale is None or sale.is_morat:
            raise GiftRefusal(SILENT, f"{catalog_id} fora do catálogo ou morat (não presenteável)")
        offer = quote(sale, currency, option)
        if offer.price <= 0:
            raise GiftRefusal(
                SILENT, f"{catalog_id} não vendido em {currency.name}, opção {option}"
            )
        first, second = sorted((sender_id, receiver.id))
        async with self._locks.of(first), self._locks.of(second):
            try:
                sent = await self._repository.send(
                    sender_id, receiver.id, currency, offer.price, catalog_id, offer.days
                )
            except InventoryConflict as e:
                raise GiftRefusal(SILENT, str(e)) from e
            if not sent:
                raise GiftRefusal(_shortage(currency), "saldo insuficiente")
            after = await self._progression.get(sender_id)
        return GiftSent(
            receiver_id=receiver.id,
            price=offer.price,
            days=offer.days,
            cash=after.cash,
            ld=after.ld,
        )

    async def page(self, account_id: int, page: int) -> GiftPage:
        number = max(page, 0)
        gifts = await self._repository.page(account_id, number, GIFT_PAGE_SIZE)
        return GiftPage(page=number, gifts=tuple(gifts))

    async def claim(self, account_id: int, slot: int) -> ItemUnit:
        async with self._locks.of(account_id):
            gift = await self._repository.pending(account_id, slot)
            if gift is None:
                raise GiftRefusal(SILENT, f"sem presente pendente com a chave {slot}")
            used = [item.inventory_index for item in await self._items.items(account_id)]
            try:
                unit = self._inventory.new_item(
                    account_id, gift.catalog_id, gift.duration_days, used
                )
            except ValueError as e:  # catálogo deixou de ser item ou não há índice livre
                raise GiftRefusal(SILENT, str(e)) from e
            try:
                claimed = await self._repository.claim(gift, unit)
            except InventoryConflict as e:
                raise GiftRefusal(SILENT, str(e)) from e
            if not claimed:
                raise GiftRefusal(SILENT, f"presente {gift.id} já foi resgatado")
            return unit
