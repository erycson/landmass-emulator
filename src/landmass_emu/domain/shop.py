"""Loja: compra por LD ou Cash (550 → 551 ou 552). Regras puras de preço, prazo e requisito, e o
`ShopService` que as aplica com saldo e inventário.

Fonte: docs/architecture/07-progression.md §5.2 (preço), §5.3 (compra) e §8 (decisões do usuário).
"""

import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol

from landmass_emu.domain.currency import Currency
from landmass_emu.domain.inventory import (
    InventoryService,
    ItemUnit,
    MoratUnit,
    enabled_gates,
)
from landmass_emu.domain.locks import AccountLocks
from landmass_emu.domain.progression import Level, RankTable
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.inventory import InventoryConflict, InventoryRepository
from landmass_emu.ports.progression import ProgressionRepository
from landmass_emu.ports.shop import ShopRepository

log = logging.getLogger(__name__)

# Prazos das opções de preço (BUY_OPTION1/7/14/30, features §2.2). O 550 manda o índice, 0 a 3.
DURATION_DAYS = (1, 7, 14, 30)
# A tela de morat mostra `buy_point[0] × 5` (LM_SupplyMoratsBuyPopPage, features §2.2).
MORAT_LD_FACTOR = 5


class BuyResult(IntEnum):
    """Resultado do 551 e do 552. `NotifyItemBuy` (XInterface, `switch`) escolhe a mensagem pelo
    valor. Saldos: `ERRCODE_CASH` e `ERRCODE_POINT`, ligados por nome a CERR_BUY_CASH_SHORTAGE
    e CERR_BUY_POINT_SHORTAGE (inferido: o valor de runtime não está no dump).
    SILENT (8000) não tem mensagem: item fora do catálogo, não vendido na moeda ou requisito não
    atendido, sem código no RE.
    """

    OK = 0
    NO_SPACE = (
        -1
    )  # msg 231000802 ("sem espaço para adquirir MO-RATS"): nenhum gate livre habilitado
    LD_SHORTAGE = -4056  # msg 231000602, "LD Insuficiente"
    CASH_SHORTAGE = -4055  # msg 231000502, "Cash insuficiente."
    SILENT = 8000  # sem mensagem na UI; o motivo vai para o log do servidor


@dataclass(frozen=True, slots=True)
class Requirements:
    """`item_required_*` (itens) e `required_*` (morats) do wdb, conferidos na compra (R-REQ-01).

    Nível e nest são conferidos. Clã, patente de clã, patente e nest_point não têm fonte no
    servidor: recusam se ≠ 0 (nenhum item do cliente tem valor). Classe, energia, força,
    agilidade e precisão são regra de equipar (F6), não de compra: a tela de morat não as usa
    para bloquear a compra.
    """

    level: int = 0
    nest: int = 0
    nest_point: int = 0
    clan: int = 0
    clan_rank: int = 0
    rank: int = 0

    def unmet(self, *, level: int, nest: int) -> str | None:
        """Motivo do primeiro requisito não atendido, ou None. `level` é a patente do comprador."""
        if self.level and level < self.level:
            return f"patente {level} abaixo de {self.level}"
        if self.nest and nest != self.nest:
            return f"nest {nest} diferente de {self.nest}"
        if self.nest_point or self.clan or self.clan_rank or self.rank:
            return "requisito sem fonte no servidor (nest_point, clã ou patente)"
        return None


@dataclass(frozen=True, slots=True)
class SaleInfo:
    """Venda de um id do catálogo: preço por opção de prazo (0 a 3) em cada moeda."""

    is_morat: bool
    ld: tuple[int, int, int, int]
    cash: tuple[int, int, int, int]
    requirements: Requirements


@dataclass(frozen=True, slots=True)
class Quote:
    price: int  # 0 = não vendido nesta moeda ou opção (R-PRC-01)
    days: int  # prazo em dias; 0 = sem prazo (morat)


def quote(sale: SaleInfo, currency: Currency, option: int) -> Quote:
    """Preço e prazo. Morat ignora a opção: a UI manda 1 e o FIXME mapeia para 0 (features §2.2)."""
    if sale.is_morat:
        if currency is Currency.LD:
            return Quote(sale.ld[0] * MORAT_LD_FACTOR, 0)
        return Quote(sale.cash[0], 0)
    if not 0 <= option < len(DURATION_DAYS):
        return Quote(0, 0)
    prices = sale.ld if currency is Currency.LD else sale.cash
    return Quote(prices[option], DURATION_DAYS[option])


class SaleCatalog(Protocol):
    def is_inventory_item(self, catalog_id: int) -> bool: ...

    def is_morat(self, catalog_id: int) -> bool: ...

    def sale(self, catalog_id: int) -> SaleInfo | None: ...


class LevelCatalog(Protocol):
    def level_list(self) -> tuple[Level, ...]: ...


class ShopRefusal(Exception):
    """Compra recusada. `morat` escolhe o opcode da resposta (551 para item, 552 para morat)."""

    def __init__(self, result: BuyResult, *, morat: bool, reason: str) -> None:
        super().__init__(reason)
        self.result = result
        self.morat = morat


@dataclass(frozen=True, slots=True)
class Purchase:
    unit: ItemUnit | MoratUnit
    cash: int  # saldos depois do débito
    ld: int
    currency: Currency = Currency.LD
    price: int = 0
    days: int = 0


def _shortage(currency: Currency) -> BuyResult:
    return BuyResult.LD_SHORTAGE if currency is Currency.LD else BuyResult.CASH_SHORTAGE


class ShopService:
    """Compra por conta, serializada por um `asyncio.Lock` (princípio 6). O preço vem do catálogo; o
    saldo e a unidade são gravados numa transação só (R-DEB-01)."""

    def __init__(
        self,
        *,
        catalog: SaleCatalog,
        levels: LevelCatalog,
        inventory: InventoryService,
        repository: InventoryRepository,
        accounts: AccountRepository,
        progression: ProgressionRepository,
        purchases: ShopRepository,
        locks: AccountLocks | None = None,
    ) -> None:
        self._catalog = catalog
        self._levels = levels
        self._inventory = inventory
        self._repository = repository
        self._accounts = accounts
        self._progression = progression
        self._purchases = purchases
        self._locks = locks or AccountLocks()

    async def buy(
        self, account_id: int, catalog_id: int, currency: Currency, option: int
    ) -> Purchase:
        async with self._locks.of(account_id):
            try:
                return await self._buy(account_id, catalog_id, currency, option)
            except ValueError as e:
                # wdb ausente ou dado inesperado: recusa sem gravar e loga como erro.
                log.error("compra de %d recusada: %s", catalog_id, e)
                raise ShopRefusal(BuyResult.SILENT, morat=False, reason=str(e)) from e

    async def _buy(
        self, account_id: int, catalog_id: int, currency: Currency, option: int
    ) -> Purchase:
        sale = self._catalog.sale(catalog_id)
        if sale is None:
            raise ShopRefusal(
                BuyResult.SILENT, morat=False, reason=f"id {catalog_id} fora do catálogo"
            )
        offer = quote(sale, currency, option)
        if offer.price <= 0:
            raise ShopRefusal(
                BuyResult.SILENT,
                morat=sale.is_morat,
                reason=f"{catalog_id} não vendido em {currency.name}, opção {option}",
            )
        progress = await self._progression.get(account_id)
        balance = progress.ld if currency is Currency.LD else progress.cash
        if balance < offer.price:
            raise ShopRefusal(
                _shortage(currency), morat=sale.is_morat, reason=f"saldo {balance} < {offer.price}"
            )
        level = self._level_of(progress.total_exp) if sale.requirements.level else 0
        nest = await self._accounts.regular_nest(account_id)
        missing = sale.requirements.unmet(level=level, nest=nest)
        if missing is not None:
            raise ShopRefusal(BuyResult.SILENT, morat=sale.is_morat, reason=missing)
        unit = await self._new_unit(account_id, catalog_id, sale, offer.days)
        try:
            debited = await self._purchases.purchase(account_id, currency, offer.price, unit)
        except InventoryConflict as e:
            raise ShopRefusal(BuyResult.SILENT, morat=sale.is_morat, reason=str(e)) from e
        if not debited:
            # O saldo mudou entre a leitura e o débito condicional: nada foi gravado.
            raise ShopRefusal(_shortage(currency), morat=sale.is_morat, reason="saldo mudou")
        after = await self._progression.get(account_id)
        return Purchase(
            unit=unit,
            cash=after.cash,
            ld=after.ld,
            currency=currency,
            price=offer.price,
            days=offer.days,
        )

    def _level_of(self, total_exp: int) -> int:
        return RankTable(self._levels.level_list()).level_for(total_exp).level

    async def _new_unit(
        self, account_id: int, catalog_id: int, sale: SaleInfo, days: int
    ) -> ItemUnit | MoratUnit:
        if sale.is_morat:
            morats = await self._repository.morats(account_id)
            used = [m.gate_index for m in morats if m.gate_index is not None]
            # R-GATE-02: morat só entra em gate habilitado (`enabled_gates`); sem vaga, NO_SPACE.
            enabled = enabled_gates(await self._accounts.gate_count(account_id), used)
            gate = next((g for g in enabled if g not in used), None)
            if gate is None:
                raise ShopRefusal(
                    BuyResult.NO_SPACE, morat=True, reason="sem gate livre habilitado"
                )
            return self._inventory.new_morat(account_id, catalog_id, gate, used)
        items = await self._repository.items(account_id)
        used_indexes = [item.inventory_index for item in items]
        return self._inventory.new_item(account_id, catalog_id, days, used_indexes)
