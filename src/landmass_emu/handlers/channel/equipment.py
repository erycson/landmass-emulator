"""Equipar, desequipar, destruir e estender no canal (F6, F7): 555, 560, 570 e 580.

Sucesso responde o opcode da resposta com `result` 0 (e o registro, quando há). Recusa responde o
mesmo tipo de resposta com `result` ≠ 0 e sem estado: o dispatcher só aplica com 0.
"""

import logging
from collections.abc import Sequence

from landmass_emu.audit import EconomyAudit, balances, unit_fields
from landmass_emu.domain.consumables import ConsumableService, Consumed, Effect, NotConsumable
from landmass_emu.domain.currency import Currency
from landmass_emu.domain.equipment import SKIN_SLOTS, EquipService, ItemRefusal, UseResult
from landmass_emu.domain.inventory import ItemUnit
from landmass_emu.domain.lifecycle import DestroyService, ExtendService
from landmass_emu.handlers.channel.login import item_record
from landmass_emu.net.server import Reply, Router
from landmass_emu.net.session import Session
from landmass_emu.protocol.equipment import (
    CsChangeMoratClassOut,
    CsChangeNestOut,
    CsEquipOp,
    CsItemConsumedOut,
    CsItemDestroyIn,
    CsItemDestroyOut,
    CsItemDestroySystemOut,
    CsItemExtendIn,
    CsItemExtendOut,
    CsItemUnusedIn,
    CsItemUnusedPieceOut,
    CsItemUsedIn,
    CsItemUsedPieceOut,
    CsItemUsedRefusedOut,
    CsItemUsedSystemOut,
    CsMoratsDestroyOut,
    CsSkinMountedOut,
    CsSkinUnusedOut,
)

log = logging.getLogger(__name__)


class EquipmentHandlers:
    def __init__(
        self,
        *,
        equip: EquipService,
        destroy: DestroyService,
        extend: ExtendService,
        consumables: ConsumableService,
        audit: EconomyAudit | None = None,
    ) -> None:
        self._equip = equip
        self._destroy = destroy
        self._extend = extend
        self._consumables = consumables
        self._audit = audit or EconomyAudit()
        self.router: Router = {
            CsEquipOp.ITEM_DESTROY_IN: self.item_destroy,
            CsEquipOp.ITEM_USED_IN: self.item_used,
            CsEquipOp.ITEM_UNUSED_IN: self.item_unused,
            CsEquipOp.ITEM_EXTEND_IN: self.item_extend,
        }

    async def item_used(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if session.account is None:
            log.warning("[%s] ItemUsed antes do login; ignorado", session.peer)
            return []
        req = CsItemUsedIn.unpack(payload)  # payload curto: struct.error, ignorado pelo roteador
        account_id = session.account.id
        try:
            done = await self._consumables.use(account_id, req.index, req.value)
        except NotConsumable:
            if req.value:
                # ItemUsedByValue fora dos consumíveis (morat principal): recusa (D75).
                return [CsItemUsedRefusedOut(UseResult.DENIED)]
            return await self._equip_item(session, account_id, req.index, req.gate)
        except ItemRefusal as refusal:
            log.info("[%s] consumir %d recusado: %s", session.peer, req.index, refusal)
            return [CsItemUsedRefusedOut(refusal.result)]
        self._audit_consumed(session, req.index, done)
        return _consumed_reply(req.index, done)

    async def _equip_item(
        self, session: Session, account_id: int, index: int, gate: int
    ) -> Sequence[Reply]:
        try:
            mounted = await self._equip.equip(account_id, index, gate)
        except ItemRefusal as refusal:
            log.info("[%s] equipar %d no gate %d recusado: %s", session.peer, index, gate, refusal)
            return [CsItemUsedRefusedOut(refusal.result)]
        log.info("[%s] equipado %d no gate %d (slot %d)", session.peer, index, gate, mounted.slot)
        if mounted.skin:
            return [CsSkinMountedOut(gate, mounted.unit.inventory_index, mounted.slot, 0)]
        if mounted.system:
            return [CsItemUsedSystemOut(item_record(mounted.unit), mounted.slot, 0)]
        return [CsItemUsedPieceOut(gate, index, mounted.slot, 0)]

    def _audit_consumed(self, session: Session, index: int, done: Consumed) -> None:
        self._audit.record(
            session,
            "use",
            catalog_id=done.unit.catalog_id,
            inventory_index=index,
            effect=done.effect.name,
            value=done.value,
            result=0,
        )

    async def item_unused(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if session.account is None:
            log.warning("[%s] ItemUnused antes do login; ignorado", session.peer)
            return []
        req = CsItemUnusedIn.unpack(payload)
        try:
            unmounted = await self._equip.unequip(session.account.id, req.index, req.gate)
        except ItemRefusal as refusal:
            log.info("[%s] desequipar %d recusado: %s", session.peer, req.index, refusal)
            return [CsItemUnusedPieceOut(req.gate, 0, refusal.result)]
        if unmounted.skin:
            return [CsSkinUnusedOut(unmounted.gate, unmounted.slot, 0)]
        return [CsItemUnusedPieceOut(unmounted.gate, unmounted.slot, 0)]

    async def item_destroy(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if session.account is None:
            log.warning("[%s] ItemDestroy antes do login; ignorado", session.peer)
            return []
        req = CsItemDestroyIn.unpack(payload)
        try:
            done = await self._destroy.destroy(session.account.id, req.catalog_id, req.index)
        except ItemRefusal as refusal:
            log.info("[%s] destruir %d recusado: %s", session.peer, req.index, refusal)
            self._audit.record(
                session,
                "destroy",
                catalog_id=req.catalog_id,
                inventory_index=req.index,
                result=int(refusal.result),
                reason=str(refusal),
            )
            return [CsItemDestroyOut(req.index, 0, False, refusal.result)]
        self._audit.record(
            session,
            "destroy",
            catalog_id=req.catalog_id,
            **(unit_fields(done.unit) if done.unit is not None else {}),
            equipped_gate=None if done.morat else done.gate,
            system_slot=done.system_slot,
            result=0,
        )
        if done.morat:
            return [CsMoratsDestroyOut(done.index, 0)]
        if done.system_slot is not None:
            return [CsItemDestroySystemOut(req.index, done.system_slot, 0)]
        gate = done.gate if done.gate is not None else 0
        unit = done.unit
        slot = unit.slot_name if isinstance(unit, ItemUnit) else None
        if slot is not None and slot in SKIN_SLOTS and done.gate is not None:
            # Pintura montada: 556 só tira o item da lista (sem mounted); 573 limpa a skin.
            return [
                CsItemDestroyOut(req.index, gate, False, 0),
                CsSkinUnusedOut(gate, SKIN_SLOTS.index(slot), 0),
            ]
        return [CsItemDestroyOut(req.index, gate, done.gate is not None, 0)]

    async def item_extend(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if session.account is None:
            log.warning("[%s] ItemExtend antes do login; ignorado", session.peer)
            return []
        req = CsItemExtendIn.unpack(payload)
        currency = Currency.LD if req.point else Currency.CASH
        try:
            done = await self._extend.extend(
                session.account.id, req.catalog_id, req.index, currency, req.option
            )
        except ItemRefusal as refusal:
            log.info("[%s] estender %d recusado: %s", session.peer, req.index, refusal)
            self._audit.record(
                session,
                "extend",
                catalog_id=req.catalog_id,
                inventory_index=req.index,
                currency=currency.name,
                option=req.option,
                result=int(refusal.result),
                reason=str(refusal),
            )
            return [CsItemExtendOut(req.index, 0, 0, 0, refusal.result)]
        self._audit.record(
            session,
            "extend",
            catalog_id=req.catalog_id,
            inventory_index=req.index,
            currency=currency.name,
            option=req.option,
            price=done.price,
            days=done.days,
            **balances(done.currency, done.price, cash=done.cash, ld=done.ld),
            expires_before=done.previous_expires_at,
            expires_after=done.expires_at,
            result=0,
        )
        # REALTIME: o cliente lê o fim em segundos Unix no apply_value (R-VAL-01).
        expires = int(done.expires_at.timestamp())
        return [CsItemExtendOut(done.index, expires, done.cash, done.ld, 0)]


def _consumed_reply(index: int, done: Consumed) -> Sequence[Reply]:
    """Resposta de sucesso por efeito. 568, 569 e 590 fazem o cliente tirar o item da lista (a chave
    é o índice); por isso não se manda 556 junto."""
    if done.effect is Effect.NEST:
        return [CsChangeNestOut(index, done.value, 0)]
    if done.effect is Effect.MORAT_CLASS:
        return [CsChangeMoratClassOut(index, done.value, 0)]
    return [CsItemConsumedOut(index, 0)]
