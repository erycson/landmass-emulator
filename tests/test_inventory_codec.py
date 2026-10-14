"""Codec do inventário: offsets do corpo de 101 (nest e gates), 102, 103, 104 e 105."""

import struct

import pytest

from landmass_emu.protocol.channel import CsInChannelServerOut, CsOp
from landmass_emu.protocol.inventory import (
    CsGetItemOut,
    CsGetMoratsOut,
    CsInventoryOp,
    CsSetRegularIn,
    CsSetRegularOut,
    _guid_bytes,
)
from landmass_emu.protocol.progression import PlayerRecord

GUID = "12345678-1234-1234-1234-123456789012"  # 36 caracteres


def test_guid_com_tamanho_errado_levanta_valueerror() -> None:
    with pytest.raises(ValueError, match="36"):
        _guid_bytes(GUID[:35])
    with pytest.raises(ValueError, match="36"):
        _guid_bytes(GUID + "x")
    assert _guid_bytes(GUID) == GUID.encode("ascii")


def test_get_item_out_offsets() -> None:
    body = CsGetItemOut(
        inventory_index=3,
        catalog_id=0x01020304,
        item_guid=GUID,
        apply_flag=2,
        apply_value=-7,
    ).pack()
    assert len(body) == 56
    assert CsGetItemOut.opcode == CsInventoryOp.GET_ITEM_OUT
    assert struct.unpack_from("<H", body, 0) == (3,)
    assert struct.unpack_from("<i", body, 4) == (0x01020304,)
    assert body[8:44] == GUID.encode("ascii")
    assert body[44] == 0  # NUL do char[37]
    assert body[0x2D] == 2
    assert struct.unpack_from("<i", body, 0x30) == (-7,)
    assert body[0x35] == 0


def test_get_morats_out_offsets() -> None:
    body = CsGetMoratsOut(
        gate_index=5,
        catalog_id=101000001,
        item_guid=GUID,
        apply_flag=2,
        apply_value=0x11223344,
    ).pack()
    assert len(body) == 96
    assert CsGetMoratsOut.opcode == CsInventoryOp.GET_MORATS_OUT
    assert struct.unpack_from("<H", body, 0) == (5,)
    assert struct.unpack_from("<i", body, 4) == (101000001,)
    assert body[8:44] == GUID.encode("ascii")
    assert body[44] == 0
    assert body[0x2D] == 2
    assert struct.unpack_from("<i", body, 0x30) == (0x11223344,)
    # 16 peças em -1 (0x34..0x53) e 3 skins em 0 (0x54..0x59).
    assert struct.unpack_from("<16h", body, 0x34) == (-1,) * 16
    assert struct.unpack_from("<3h", body, 0x54) == (0, 0, 0)
    assert body[0x5D] == 0


def test_set_regular_in_le_nest_e_classe() -> None:
    assert CsSetRegularIn.opcode == CsInventoryOp.SET_REGULAR_IN
    assert CsSetRegularIn.unpack(b"\x02\x03") == CsSetRegularIn(nest=2, morat_class=3)
    # Bytes além dos dois primeiros são ignorados.
    assert CsSetRegularIn.unpack(b"\x02\x03\xff") == CsSetRegularIn(nest=2, morat_class=3)


@pytest.mark.parametrize("payload", [b"", b"\x02"])
def test_set_regular_in_curto_levanta_struct_error(payload: bytes) -> None:
    # Diferente dos outros `unpack` do canal (que levantam ValueError). O `Service` captura os dois.
    with pytest.raises(struct.error):
        CsSetRegularIn.unpack(payload)


def test_set_regular_out_corpo_vazio() -> None:
    assert CsSetRegularOut.opcode == CsInventoryOp.SET_REGULAR_OUT
    assert CsSetRegularOut().pack() == b""


def test_101_leva_nest_e_gates_nos_offsets_do_lm_player_info() -> None:
    progress = PlayerRecord(nest=2, enabled_gates=(0, 3))
    body = CsInChannelServerOut(client_guid=7, result=0, progress=progress).pack()
    assert len(body) == 176
    assert CsInChannelServerOut.opcode == CsOp.IN_CHANNEL_SERVER_OUT
    assert struct.unpack_from("<i", body, 0x90) == (7,)
    assert struct.unpack_from("<i", body, 0xA0) == (7,)
    assert struct.unpack_from("<i", body, 0xA8) == (0,)
    assert body[0x20] == 2
    for gate in (0, 3):
        base = 0x5A + 4 * gate
        assert struct.unpack_from("<h", body, base) == (gate,)
        assert body[base + 2] == 1
    for gate in (1, 2, 4, 5, 6, 7):
        assert struct.unpack_from("<hB", body, 0x5A + 4 * gate) == (0, 0)


def test_101_grava_o_result_e_recusa_gate_fora_da_faixa() -> None:
    body = CsInChannelServerOut(client_guid=7, result=-160).pack()
    assert struct.unpack_from("<i", body, 0xA8) == (-160,)
    for gate in (-1, 8):
        with pytest.raises(ValueError, match="gate"):
            progress = PlayerRecord(enabled_gates=(gate,))
            CsInChannelServerOut(client_guid=7, result=0, progress=progress).pack()
