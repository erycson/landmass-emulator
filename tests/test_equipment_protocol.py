"""Codecs de equipar, desequipar, destruir e estender (554 a 585): tamanho e offsets do corpo,
conferidos contra o dispatcher (re/protocol_full.md §3.1 e §3.2)."""

import struct

import pytest

from landmass_emu.protocol.equipment import (
    CsItemDestroyIn,
    CsItemDestroyOut,
    CsItemDestroySystemOut,
    CsItemEndtimeOut,
    CsItemExtendIn,
    CsItemExtendOut,
    CsItemUnusedIn,
    CsItemUnusedPieceOut,
    CsItemUsedIn,
    CsItemUsedPieceOut,
    CsItemUsedRefusedOut,
    CsItemUsedSystemOut,
    CsMoratsDestroyOut,
)
from landmass_emu.protocol.inventory import CsGetItemOut


def _registro() -> CsGetItemOut:
    return CsGetItemOut(
        inventory_index=5,
        catalog_id=308000001,
        item_guid="g" * 36,
        apply_flag=2,
        apply_value=1700000000,
    )


def test_pedidos_leem_os_offsets_do_corpo() -> None:
    assert CsItemDestroyIn.unpack(struct.pack("<iH", 1000100, 5)) == CsItemDestroyIn(1000100, 5)
    assert CsItemUsedIn.unpack(struct.pack("<HHi", 5, 2, 0)) == CsItemUsedIn(5, 2, 0)
    assert CsItemUnusedIn.unpack(struct.pack("<HH", 5, 2)) == CsItemUnusedIn(5, 2)
    assert CsItemExtendIn.unpack(struct.pack("<iHBB", 1000100, 5, 1, 2)) == CsItemExtendIn(
        1000100, 5, True, 2
    )


def test_pedido_curto_levanta_struct_error() -> None:
    with pytest.raises(struct.error):
        CsItemUsedIn.unpack(b"\x00\x01")


def test_554_leva_o_registro_do_item_slot_e_resultado() -> None:
    raw = CsItemUsedSystemOut(_registro(), slot=3, result=0).pack()
    assert len(raw) == 0x3C
    assert raw[:0x34] == _registro().pack()[:0x34]
    assert struct.unpack_from("<H", raw, 0x34) == (3,)
    assert struct.unpack_from("<i", raw, 0x38) == (0,)


def test_556_leva_indice_gate_flag_e_resultado() -> None:
    raw = CsItemDestroyOut(index=5, gate=2, mounted=True, result=0).pack()
    assert len(raw) == 12
    assert struct.unpack_from("<HHBxxxi", raw) == (5, 2, 1, 0)


def test_556_sem_montagem_manda_flag_zero() -> None:
    raw = CsItemDestroyOut(index=5, gate=0, mounted=False, result=-4).pack()
    assert struct.unpack_from("<HHBxxxi", raw) == (5, 0, 0, -4)


def test_559_troca_o_gate_pelo_slot_de_sistema() -> None:
    raw = CsItemDestroySystemOut(index=5, slot=2, result=0).pack()
    assert len(raw) == 12
    assert struct.unpack_from("<HHBxxxi", raw) == (5, 2, 1, 0)


def test_557_leva_o_gate_e_o_resultado() -> None:
    raw = CsMoratsDestroyOut(gate=1, result=0).pack()
    assert raw == struct.pack("<Hxxi", 1, 0)


def test_561_so_leva_o_resultado_em_8() -> None:
    raw = CsItemUsedRefusedOut(-7).pack()
    assert len(raw) == 12
    assert raw[:8] == bytes(8)
    assert struct.unpack_from("<i", raw, 8) == (-7,)


def test_562_leva_gate_indice_slot_e_resultado() -> None:
    raw = CsItemUsedPieceOut(gate=0, index=7, slot=4, result=0).pack()
    assert len(raw) == 12
    assert struct.unpack_from("<H", raw, 0) == (0,)
    assert struct.unpack_from("<H", raw, 2) == (7,)
    assert raw[4:6] == bytes(2)
    assert struct.unpack_from("<H", raw, 6) == (4,)
    assert struct.unpack_from("<i", raw, 8) == (0,)


def test_572_leva_gate_slot_e_resultado() -> None:
    raw = CsItemUnusedPieceOut(gate=1, slot=9, result=0).pack()
    assert len(raw) == 12
    assert struct.unpack_from("<HxxHxxi", raw) == (1, 9, 0)


def test_582_leva_indice_prazo_saldos_e_resultado() -> None:
    raw = CsItemExtendOut(index=5, apply_value=1800000000, cash=10, point=700, result=0).pack()
    assert len(raw) == 20
    assert struct.unpack_from("<Hxxiiii", raw) == (5, 1800000000, 10, 700, 0)


def test_585_leva_premium_zero_item_um_e_indice() -> None:
    assert CsItemEndtimeOut(index=5).pack() == struct.pack("<BBH", 0, 1, 5)
