"""Depósito e presente no canal (F10): 615 envia por nick, 610 lista o Depósito e 612 resgata.

Envio responde 616 (com `result` 0 e os saldos do remetente, ou um código negativo) e avisa o
destinatário online com 617. A listagem responde 611 com a página. O resgate responde 613,
com o item que o cliente grava no hangar sem relogar. Regras em `domain/gift.py`.
"""

import logging
from collections.abc import Sequence

from landmass_emu.audit import EconomyAudit, balances, unit_fields
from landmass_emu.domain.currency import Currency
from landmass_emu.domain.gift import Gift, GiftRefusal, GiftService
from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.shop import DURATION_DAYS
from landmass_emu.handlers.channel.login import item_record
from landmass_emu.net.server import Reply, reply_body
from landmass_emu.net.session import Session
from landmass_emu.protocol.gift import (
    CsGetGiftItemIn,
    CsGetGiftItemOut,
    CsGiftItemUsedIn,
    CsGiftItemUsedOut,
    CsGiftNoticeOut,
    CsItemGiftIn,
    CsItemGiftOut,
    GiftLine,
)
from landmass_emu.protocol.header import CHANNEL_NET_CODE

log = logging.getLogger(__name__)


class GiftHandlers:
    def __init__(self, gifts: GiftService, lobby: Lobby, audit: EconomyAudit | None = None) -> None:
        self._gifts = gifts
        self._lobby = lobby
        self._audit = audit or EconomyAudit()

    async def item_gift(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if session.account is None:
            log.warning("[%s] ItemGift antes do login; ignorado", session.peer)
            return []
        req = CsItemGiftIn.unpack(payload)  # payload curto: struct.error, ignorado pelo roteador
        currency = Currency.LD if req.point else Currency.CASH
        try:
            sent = await self._gifts.send(
                session.account.id, req.nick, req.catalog_id, currency, req.option
            )
        except GiftRefusal as refusal:
            log.info("[%s] presente de %d recusado: %s", session.peer, req.catalog_id, refusal)
            self._audit.record(
                session,
                "gift",
                action="send",
                catalog_id=req.catalog_id,
                currency=currency.name,
                option=req.option,
                receiver=req.nick,
                result=refusal.result,
                reason=str(refusal),
            )
            return [CsItemGiftOut(refusal.result)]
        self._audit.record(
            session,
            "gift",
            action="send",
            catalog_id=req.catalog_id,
            currency=currency.name,
            option=req.option,
            receiver=req.nick,
            receiver_id=sent.receiver_id,
            price=sent.price,
            days=sent.days,
            **balances(currency, sent.price, cash=sent.cash, ld=sent.ld),
            result=0,
        )
        # Destinatário online recebe o aviso (617); offline vê o presente ao abrir o Depósito.
        guid = self._lobby.guid_of_nick(req.nick)
        if guid is not None:
            self._lobby.send_to([guid], reply_body(CsGiftNoticeOut(), CHANNEL_NET_CODE))
        return [CsItemGiftOut(0, sent.cash, sent.ld)]

    async def get_gift_item(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if session.account is None:
            log.warning("[%s] GetGiftItem antes do login; ignorado", session.peer)
            return []
        req = CsGetGiftItemIn.unpack(payload)
        page = await self._gifts.page(session.account.id, req.page)
        return [CsGetGiftItemOut(page.page, tuple(_line(gift) for gift in page.gifts))]

    async def gift_item_used(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if session.account is None:
            log.warning("[%s] GiftItemUsed antes do login; ignorado", session.peer)
            return []
        req = CsGiftItemUsedIn.unpack(payload)
        try:
            unit = await self._gifts.claim(session.account.id, req.key)
        except GiftRefusal as refusal:
            log.info("[%s] resgate %d recusado: %s", session.peer, req.key, refusal)
            self._audit.record(
                session,
                "gift",
                action="claim",
                key=req.key,
                result=refusal.result,
                reason=str(refusal),
            )
            return [CsGiftItemUsedOut(refusal.result, req.key)]
        self._audit.record(
            session,
            "gift",
            action="claim",
            key=req.key,
            catalog_id=unit.catalog_id,
            **unit_fields(unit),
            result=0,
        )
        return [CsGiftItemUsedOut(0, req.key, item_record(unit))]


def _line(gift: Gift) -> GiftLine:
    return GiftLine(
        key=gift.slot,
        catalog_id=gift.catalog_id,
        item_guid=f"gift-{gift.id}",
        buy_option=DURATION_DAYS.index(gift.duration_days),
    )
