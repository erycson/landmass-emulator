"""Codecs da loja: compra (550) e resultado (551 para item, 552 para morat). Offsets do corpo,
depois do cabeçalho u16 (re/protocol_full.md §3.1 e §3.2)."""

import struct

from landmass_emu.protocol.inventory import CsGetItemOut, CsGetMoratsOut
from landmass_emu.protocol.shop import CsItemBuyIn, CsItemBuyOut, CsMoratsBuyOut, CsShopOp

GUID = "a" * 36
ITEM = CsGetItemOut(
    inventory_index=3,
    catalog_id=1000100,
    item_guid=GUID,
    apply_flag=2,
    apply_value=1700000000,
)
MORAT = CsGetMoratsOut(
    gate_index=2,
    catalog_id=101000001,
    item_guid=GUID,
    apply_flag=0,
    apply_value=0,
)


def test_opcodes_da_loja() -> None:
    assert (CsShopOp.ITEM_BUY_IN, CsShopOp.ITEM_BUY_OUT, CsShopOp.MORATS_BUY_OUT) == (
        550,
        551,
        552,
    )


def test_compra_550_decodifica_id_moeda_e_prazo() -> None:
    payload = struct.pack("<iBB", 101000001, 1, 2) + bytes(6)
    assert CsItemBuyIn.unpack(payload) == CsItemBuyIn(101000001, True, 2)


def test_compra_550_ida_e_volta_com_corpo_de_12_bytes() -> None:
    pedido = CsItemBuyIn(1000100, False, 3)
    corpo = pedido.pack()
    assert len(corpo) == 12
    # bPoint @4 = 0 (Cash) e nBuyOption @5 = 3.
    assert corpo[4:6] == bytes([0, 3])
    assert CsItemBuyIn.unpack(corpo) == pedido


def test_551_com_item_tem_registro_de_0x34_e_saldos_em_0x38() -> None:
    corpo = CsItemBuyOut(result=0, cash=50, point=700, item=ITEM).pack()
    assert len(corpo) == 0x44
    assert corpo[:0x34] == ITEM.pack()[:0x34]
    assert struct.unpack_from("<H", corpo, 0)[0] == 3
    assert struct.unpack_from("<iii", corpo, 0x38) == (50, 700, 0)


def test_551_recusa_vai_sem_registro_e_com_resultado_em_0x40() -> None:
    corpo = CsItemBuyOut(result=-4055, cash=0, point=0).pack()
    assert len(corpo) == 0x44
    assert corpo[:0x34] == bytes(0x34)
    assert struct.unpack_from("<iii", corpo, 0x38) == (0, 0, -4055)


def test_552_com_morat_tem_registro_de_0x5c_e_saldos_em_0x5c() -> None:
    corpo = CsMoratsBuyOut(result=0, cash=20, point=25000, morat=MORAT).pack()
    assert len(corpo) == 0x68
    assert corpo[:0x5C] == MORAT.pack()[:0x5C]
    assert struct.unpack_from("<iii", corpo, 0x5C) == (20, 25000, 0)


def test_552_recusa_vai_com_resultado_em_0x64() -> None:
    corpo = CsMoratsBuyOut(result=-1, cash=0, point=0).pack()
    assert len(corpo) == 0x68
    assert struct.unpack_from("<i", corpo, 0x64)[0] == -1
