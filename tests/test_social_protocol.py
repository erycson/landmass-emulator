"""Codecs de amigos, bloqueios e sussurro (F12). Offsets de tools/re/protocol_full.md §2.1 e
§2.2."""

import struct

import pytest

from landmass_emu.protocol.message import (
    MAX_RELATION_IDS,
    MAX_WHISPER_TEXT,
    MsAccountIdIn,
    MsBlackListOut,
    MsContactRecord,
    MsDelFriendOut,
    MsFriendListOut,
    MsNickIn,
    MsRefreshFriendOut,
    MsRelationIdsIn,
    MsRelationState,
    MsResult,
    MsSendWhisperIn,
    MsWhisperErrorOut,
    MsWhisperOut,
)


def _nick(name: str) -> bytes:
    return name.encode().ljust(18, b"\0")


def test_registro_de_amigo_tem_0x2c_bytes_nos_offsets_do_cliente() -> None:
    body = MsFriendListOut(MsContactRecord(7, "Ana", total_exp=2800, online=True)).pack()
    assert len(body) == 0x2C
    assert struct.unpack_from("<i", body, 0x00) == (7,)
    assert body[0x04:0x14].split(b"\0", 1)[0] == b"Ana"
    assert body[0x14] == 0  # NUL do nick: o cliente lê até aqui
    assert struct.unpack_from("<i", body, 0x20) == (2800,)
    assert body[0x25] == 0x22
    assert struct.unpack_from("<i", body, 0x28) == (0,)  # gate: 0 aceita


def test_registro_recusado_leva_o_resultado_no_gate() -> None:
    body = MsBlackListOut(MsContactRecord(0, "Ninguem", result=MsResult.INVALID_VALUE)).pack()
    assert struct.unpack_from("<i", body, 0x28) == (-11,)
    assert body[0x25] == 0


def test_nick_de_16_bytes_mantem_o_nul_em_0x14() -> None:
    body = MsFriendListOut(MsContactRecord(1, "A" * 16)).pack()
    assert body[0x04:0x14] == b"A" * 16
    assert body[0x14] == 0


def test_pedido_de_nick_ida_e_volta_com_17_bytes() -> None:
    payload = MsNickIn("Ana").pack()
    assert len(payload) == 17
    assert MsNickIn.unpack(payload) == MsNickIn("Ana")
    with pytest.raises(struct.error):
        MsNickIn.unpack(b"Ana")


def test_pedido_de_remocao_ida_e_volta_com_id_em_0() -> None:
    assert MsAccountIdIn.unpack(MsAccountIdIn(9).pack()) == MsAccountIdIn(9)
    assert MsAccountIdIn(9).pack() == struct.pack("<i", 9)


def test_resposta_de_remocao_ecoa_o_id_em_0_e_o_resultado_em_4() -> None:
    assert MsDelFriendOut(9, 0).pack() == struct.pack("<ii", 9, 0)
    assert MsDelFriendOut(9, -11).pack() == struct.pack("<ii", 9, -11)


def test_pedido_de_lote_ida_e_volta_com_ids_a_partir_de_4() -> None:
    payload = MsRelationIdsIn((5, 6)).pack()
    assert payload[0] == 2
    assert struct.unpack_from("<ii", payload, 4) == (5, 6)
    assert MsRelationIdsIn.unpack(payload) == MsRelationIdsIn((5, 6))


def test_pedido_de_lote_recusa_contagem_fora_da_faixa_e_payload_curto() -> None:
    with pytest.raises(ValueError):
        MsRelationIdsIn.unpack(struct.pack("<B3x", 0))
    too_many = MsRelationIdsIn(tuple(range(MAX_RELATION_IDS + 1))).pack()
    with pytest.raises(ValueError):
        MsRelationIdsIn.unpack(too_many)
    with pytest.raises(struct.error):
        MsRelationIdsIn.unpack(struct.pack("<B3x", 2) + struct.pack("<i", 5))


def test_lote_de_resposta_tem_contagem_em_0_e_registros_de_0x14() -> None:
    body = MsRefreshFriendOut((MsRelationState(5, 2800, online=True), MsRelationState(6, 0))).pack()
    assert len(body) == 4 + 2 * 0x14
    assert body[0] == 2
    assert struct.unpack_from("<iiii", body, 4) == (5, 2800, 0, 0)
    assert body[4 + 0x10] == 0  # nest
    assert body[4 + 0x11] == 0x22
    assert struct.unpack_from("<i", body, 4 + 0x14) == (6,)
    assert body[4 + 0x14 + 0x11] == 0


def test_sussurro_de_entrada_ida_e_volta_com_destinatario_len_e_texto() -> None:
    payload = MsSendWhisperIn("Ana", b"oi!").pack()
    assert payload[:18] == _nick("Ana")
    assert struct.unpack_from("<H", payload, 0x12) == (3,)
    assert payload[0x14:] == b"oi!"
    assert MsSendWhisperIn.unpack(payload) == MsSendWhisperIn("Ana", b"oi!")


def test_sussurro_acima_de_0x78_ou_truncado_e_recusado() -> None:
    too_long = MsSendWhisperIn("Ana", b"x" * (MAX_WHISPER_TEXT + 1)).pack()
    with pytest.raises(ValueError):
        MsSendWhisperIn.unpack(too_long)
    truncated = _nick("Ana") + struct.pack("<H", 5) + b"oi"
    with pytest.raises(ValueError):
        MsSendWhisperIn.unpack(truncated)
    with pytest.raises(struct.error):
        MsSendWhisperIn.unpack(b"Ana")


def test_sussurro_de_saida_e_de_erro_tem_os_offsets_da_recepcao() -> None:
    out = MsWhisperOut("Ana", b"oi!").pack()
    assert out[:18] == _nick("Ana")
    assert struct.unpack_from("<H", out, 0x12) == (3,)
    assert out[0x14:] == b"oi!"

    err = MsWhisperErrorOut(MsResult.CONTACT_OFFLINE, "Bia", b"oi!").pack()
    assert struct.unpack_from("<i", err, 0) == (-19,)
    assert err[4:22] == _nick("Bia")
    assert struct.unpack_from("<H", err, 0x16) == (3,)
    assert err[0x18:] == b"oi!"
