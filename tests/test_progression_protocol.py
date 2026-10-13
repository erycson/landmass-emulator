import struct

import pytest

from landmass_emu.protocol.channel import CsInChannelServerOut, CsOp
from landmass_emu.protocol.progression import (
    CsChargeCashOut,
    CsChargePointOut,
    CsProgressionOp,
    CsTutorialClearIn,
    CsTutorialClearOut,
    PlayerRecord,
)


def test_player_record_tamanho_e_offsets_de_progressao() -> None:
    raw = PlayerRecord(tutorial_clear=5, total_exp=2800, cash=500, point=1000).pack(7)
    assert len(raw) == 0xA8
    assert struct.unpack_from("<i", raw, 0x28) == (5,)  # iTutorialClear → nó+0x38
    assert struct.unpack_from("<i", raw, 0x2C) == (2800,)  # iTotalExp → nó+0x3c
    assert struct.unpack_from("<i", raw, 0x48) == (500,)  # iCash → nó+0x58
    assert struct.unpack_from("<i", raw, 0x4C) == (1000,)  # iPoint → nó+0x5c
    assert struct.unpack_from("<i", raw, 0x90) == (7,)
    assert struct.unpack_from("<i", raw, 0xA0) == (7,)
    # Os campos fora de progressão ficam zero.
    assert raw[0x00:0x28] == bytes(0x28)
    assert raw[0x30:0x48] == bytes(0x18)
    assert raw[0x50:0x90] == bytes(0x40)


def test_player_record_padrao_so_leva_o_id() -> None:
    raw = PlayerRecord().pack(9)
    assert struct.unpack_from("<i", raw, 0x90) == (9,)
    assert raw[0x28:0x30] == bytes(8)
    assert raw[0x48:0x50] == bytes(8)


def test_101_com_progressao_mantem_o_tamanho_e_o_resultado() -> None:
    raw = CsInChannelServerOut(
        client_guid=7, result=0, progress=PlayerRecord(total_exp=2800, point=1000)
    ).pack()
    assert len(raw) == 0xB0
    assert struct.unpack_from("<i", raw, 0x2C) == (2800,)
    assert struct.unpack_from("<i", raw, 0x4C) == (1000,)
    assert struct.unpack_from("<i", raw, 0xA8) == (0,)
    assert struct.unpack_from("<i", raw, 0xAC) == (0,)
    assert CsInChannelServerOut.opcode == CsOp.IN_CHANNEL_SERVER_OUT


def test_tutorial_in_ida_e_volta() -> None:
    assert CsTutorialClearIn(2).pack() == b"\x02"
    assert CsTutorialClearIn.unpack(b"\x02") == CsTutorialClearIn(2)
    assert CsTutorialClearIn.unpack(b"\x01\xff") == CsTutorialClearIn(1)  # extra é ignorado


def test_tutorial_in_payload_vazio_levanta_struct_error() -> None:
    with pytest.raises(struct.error):
        CsTutorialClearIn.unpack(b"")


def test_tutorial_out_tamanho_e_offsets() -> None:
    raw = CsTutorialClearOut(tutorial_clear=5, point=1000).pack()
    assert len(raw) == 8
    assert struct.unpack_from("<i", raw, 0) == (5,)
    assert struct.unpack_from("<i", raw, 4) == (1000,)
    assert CsTutorialClearOut.opcode == CsProgressionOp.TUTORIAL_CLEAR_OUT == 601


def test_pushes_de_saldo_tamanho_e_opcode() -> None:
    assert CsChargeCashOut(500).pack() == struct.pack("<i", 500)
    assert CsChargePointOut(1000).pack() == struct.pack("<i", 1000)
    assert CsChargeCashOut.opcode == 900
    assert CsChargePointOut.opcode == 902
