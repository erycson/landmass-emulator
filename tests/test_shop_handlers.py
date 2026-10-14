"""Handlers da loja no canal: 550 chama a loja e responde 551 ou 552, com registro, saldos e
resultado. Recusa vai com o código e sem registro."""

import struct
from datetime import UTC, datetime

from landmass_emu.domain.account import Account
from landmass_emu.domain.currency import Currency
from landmass_emu.domain.inventory import ApplyFlag, ItemUnit, MoratUnit
from landmass_emu.domain.shop import BuyResult, Purchase, ShopRefusal
from landmass_emu.handlers.channel.shop import ShopHandlers
from landmass_emu.net.session import Session
from landmass_emu.protocol.inventory import CsGetItemOut, CsGetMoratsOut
from landmass_emu.protocol.progression import CsChargeCashOut, CsChargePointOut
from landmass_emu.protocol.shop import CsItemBuyIn, CsItemBuyOut, CsMoratsBuyOut

GUID = "c" * 36
ANA = Account(id=1, username="ana", nickname="Ana", token_hash="x")


class LojaFalsa:
    """Devolve a compra pronta ou levanta a recusa, e guarda os pedidos recebidos."""

    def __init__(self, desfecho: Purchase | ShopRefusal) -> None:
        self._desfecho = desfecho
        self.chamadas: list[tuple[int, int, Currency, int]] = []

    async def buy(
        self, account_id: int, catalog_id: int, currency: Currency, option: int
    ) -> Purchase:
        self.chamadas.append((account_id, catalog_id, currency, option))
        if isinstance(self._desfecho, ShopRefusal):
            raise self._desfecho
        return self._desfecho


def _unidade_item() -> ItemUnit:
    return ItemUnit(
        account_id=1,
        inventory_index=1,
        catalog_id=1000100,
        item_guid=GUID,
        apply_flag=ApplyFlag.REALTIME,
        apply_value=None,
        expires_at=datetime(2026, 11, 1, tzinfo=UTC),
    )


def _unidade_morat() -> MoratUnit:
    return MoratUnit(
        account_id=1,
        inventory_index=2,
        catalog_id=101000001,
        item_guid=GUID,
        gate_index=2,
        apply_flag=ApplyFlag.UNLIMIT,
        apply_value=None,
        expires_at=None,
    )


async def test_sem_login_nao_compra_e_nao_responde() -> None:
    loja = LojaFalsa(Purchase(unit=_unidade_item(), cash=0, ld=0))
    pedido = CsItemBuyIn(1000100, True, 1).pack()
    respostas = await ShopHandlers(loja).item_buy(Session(peer="t"), pedido)
    assert list(respostas) == []
    assert loja.chamadas == []


async def test_compra_de_item_responde_551_102_e_saldos() -> None:
    loja = LojaFalsa(Purchase(unit=_unidade_item(), cash=50, ld=700))
    pedido = CsItemBuyIn(1000100, True, 1).pack()
    respostas = await ShopHandlers(loja).item_buy(Session(peer="t", account=ANA), pedido)
    assert [type(r) for r in respostas] == [
        CsItemBuyOut,
        CsGetItemOut,
        CsChargeCashOut,
        CsChargePointOut,
    ]
    assert respostas[0].result == BuyResult.OK
    assert (respostas[0].cash, respostas[0].point) == (50, 700)
    assert loja.chamadas == [(1, 1000100, Currency.LD, 1)]


async def test_compra_de_morat_responde_552_103_e_saldos() -> None:
    loja = LojaFalsa(Purchase(unit=_unidade_morat(), cash=0, ld=5000))
    pedido = CsItemBuyIn(101000001, False, 0).pack()
    respostas = await ShopHandlers(loja).item_buy(Session(peer="t", account=ANA), pedido)
    assert [type(r) for r in respostas] == [
        CsMoratsBuyOut,
        CsGetMoratsOut,
        CsChargeCashOut,
        CsChargePointOut,
    ]
    assert loja.chamadas == [(1, 101000001, Currency.CASH, 0)]


async def test_recusa_de_item_responde_551_sem_registro_e_com_codigo() -> None:
    recusa = ShopRefusal(BuyResult.CASH_SHORTAGE, morat=False, reason="saldo 10 < 30")
    loja = LojaFalsa(recusa)
    pedido = CsItemBuyIn(1000100, False, 1).pack()
    respostas = await ShopHandlers(loja).item_buy(Session(peer="t", account=ANA), pedido)
    assert len(respostas) == 1
    assert isinstance(respostas[0], CsItemBuyOut)
    assert respostas[0].result == BuyResult.CASH_SHORTAGE
    assert (respostas[0].cash, respostas[0].point) == (0, 0)
    assert struct.unpack_from("<i", respostas[0].pack(), 0x40)[0] == -4055


async def test_recusa_de_morat_responde_552_com_codigo_de_sem_gate() -> None:
    recusa = ShopRefusal(BuyResult.NO_SPACE, morat=True, reason="sem gate livre")
    loja = LojaFalsa(recusa)
    pedido = CsItemBuyIn(101000001, True, 0).pack()
    respostas = await ShopHandlers(loja).item_buy(Session(peer="t", account=ANA), pedido)
    assert len(respostas) == 1
    assert isinstance(respostas[0], CsMoratsBuyOut)
    assert struct.unpack_from("<i", respostas[0].pack(), 0x64)[0] == -1
