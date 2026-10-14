"""Loja no canal: 550 compra por LD ou Cash.

Sucesso responde 551 (item) ou 552 (morat), seguido do 102 ou 103 da unidade nova e dos saldos
(900 Cash e 902 LD). Recusa responde o mesmo opcode com resultado ≠ 0 e sem registro.
"""

import logging
from collections.abc import Sequence

from landmass_emu.audit import EconomyAudit, balances, unit_fields
from landmass_emu.domain.currency import Currency
from landmass_emu.domain.inventory import MoratUnit
from landmass_emu.domain.shop import BuyResult, Purchase, ShopRefusal, ShopService
from landmass_emu.handlers.channel.login import item_record, morat_record
from landmass_emu.net.server import Reply
from landmass_emu.net.session import Session
from landmass_emu.protocol.progression import CsChargeCashOut, CsChargePointOut
from landmass_emu.protocol.shop import CsItemBuyIn, CsItemBuyOut, CsMoratsBuyOut

log = logging.getLogger(__name__)


class ShopHandlers:
    def __init__(self, shop: ShopService, audit: EconomyAudit | None = None) -> None:
        self._shop = shop
        self._audit = audit or EconomyAudit()

    async def item_buy(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if session.account is None:
            log.warning("[%s] ItemBuy antes do login; ignorado", session.peer)
            return []
        req = CsItemBuyIn.unpack(payload)  # payload curto: struct.error, ignorado pelo roteador
        currency = Currency.LD if req.point else Currency.CASH
        try:
            purchase = await self._shop.buy(
                session.account.id, req.catalog_id, currency, req.option
            )
        except ShopRefusal as refusal:
            log.info("[%s] compra de %d recusada: %s", session.peer, req.catalog_id, refusal)
            self._audit.record(
                session,
                "buy",
                catalog_id=req.catalog_id,
                currency=currency.name,
                option=req.option,
                result=int(refusal.result),
                reason=str(refusal),
            )
            return _refused(refusal.morat, refusal.result)
        log.info("[%s] compra de %d (%s) aprovada", session.peer, req.catalog_id, currency.name)
        self._audit.record(
            session,
            "buy",
            catalog_id=req.catalog_id,
            currency=currency.name,
            option=req.option,
            price=purchase.price,
            days=purchase.days,
            **balances(purchase.currency, purchase.price, cash=purchase.cash, ld=purchase.ld),
            **unit_fields(purchase.unit),
            result=0,
        )
        return _bought(purchase)


def _refused(morat: bool, result: BuyResult) -> list[Reply]:
    if morat:
        return [CsMoratsBuyOut(result=result, cash=0, point=0)]
    return [CsItemBuyOut(result=result, cash=0, point=0)]


def _bought(purchase: Purchase) -> list[Reply]:
    # Resultado, unidade (102 ou 103, para o item aparecer sem relogar) e saldos (900, 902).
    saldos: list[Reply] = [CsChargeCashOut(purchase.cash), CsChargePointOut(purchase.ld)]
    if isinstance(purchase.unit, MoratUnit):
        morat = morat_record(purchase.unit)
        head = CsMoratsBuyOut(BuyResult.OK, purchase.cash, purchase.ld, morat=morat)
        return [head, morat, *saldos]
    item = item_record(purchase.unit)
    return [CsItemBuyOut(BuyResult.OK, purchase.cash, purchase.ld, item=item), item, *saldos]
