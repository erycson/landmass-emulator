"""Codecs de clã (F13) com os offsets que o cliente lê: 172, 175, 177, 178 e 195.

Fontes: tools/re/protocol_full.md §2.1 e §2.2;
tools/re/LM_Engine.dll/message_dispatch_FUN_10025120.c
(cases 0xac, 0xaf, 0xb2, 0xc3); `execGetClanInfo` (tools/re/LM_Engine.dll/all/1000a6c0)."""

import struct

import pytest

from landmass_emu.protocol.message import (
    MsClanChatIn,
    MsClanChatOut,
    MsClanInfoOut,
    MsClanMemberOut,
    MsClanRecord,
    MsRefreshClanOut,
)


def test_172_tem_88_bytes_com_offsets_decodificados() -> None:
    body = MsClanInfoOut(clan_id=7, name="Nova", master="Ana", mark=3).pack()

    assert len(body) == 88
    assert struct.unpack_from("<i", body, 0x18)[0] == 7  # id do clã (node+0x28 no cliente)
    assert struct.unpack_from("<i", body, 0x4C)[0] == 3  # marca (node+0x2C)
    assert body[0x50] == 0  # node+0x30, sem leitor
    assert body[4:9] == b"Nova\0"  # nome (inferido: execGetClanInfo lê node+0x1C)
    assert body[0x1D:0x21] == b"Ana\0"  # mestre (inferido: execGetClanInfo lê node+0x35)


def test_172_nome_de_16_caracteres_nao_invade_o_id() -> None:
    body = MsClanInfoOut(clan_id=9, name="N" * 16, master="M", mark=0).pack()

    assert body[4:20] == b"N" * 16
    assert body[20] == 0
    assert struct.unpack_from("<i", body, 0x18)[0] == 9


def test_175_tem_chave_i16_nick_estado_e_exp() -> None:
    body = MsClanMemberOut(42, "Ana", 1500, online=True).pack()

    assert len(body) == 0x20
    assert struct.unpack_from("<h", body, 0)[0] == 42
    assert body[2:6] == b"Ana\0"
    assert body[0x14] == 0x22  # estado conectado
    assert struct.unpack_from("<i", body, 0x18)[0] == 1500
    assert body[0x1C] == 0  # +0x23 sem leitor identificado


def test_175_offline_leva_estado_zero() -> None:
    body = MsClanMemberOut(1, "Bia").pack()

    assert body[0x14] == 0


def test_177_le_texto_a_partir_de_2() -> None:
    payload = struct.pack("<H", 3) + b"oi!" + b"lixo"

    assert MsClanChatIn.unpack(payload).text == b"oi!"


def test_177_recusa_len_acima_de_0x78() -> None:
    payload = struct.pack("<H", 0x79) + b"x" * 0x79

    with pytest.raises(ValueError, match="inconsistente"):
        MsClanChatIn.unpack(payload)


def test_177_recusa_payload_curto() -> None:
    payload = struct.pack("<H", 5) + b"ab"

    with pytest.raises(ValueError, match="inconsistente"):
        MsClanChatIn.unpack(payload)


def test_178_tem_remetente_len_e_texto_nos_offsets_de_161() -> None:
    body = MsClanChatOut("Ana", b"oi").pack()

    assert len(body) == 0x16
    assert body[0:4] == b"Ana\0"
    assert struct.unpack_from("<H", body, 0x12)[0] == 2
    assert body[0x14:0x16] == b"oi"


def test_195_cabecalho_de_12_bytes_e_registros_de_12() -> None:
    body = MsRefreshClanOut(7, 3, (MsClanRecord(42, 1500, online=True),)).pack()

    assert len(body) == 0x0C + 0x0C
    assert struct.unpack_from("<iiBB", body, 0) == (7, 3, 0, 1)  # count @9
    assert struct.unpack_from("<iiB", body, 0x0C) == (42, 1500, 0x22)


def test_195_lote_vazio_tem_so_o_cabecalho() -> None:
    body = MsRefreshClanOut(7, 0, ()).pack()

    assert len(body) == 0x0C
    assert body[9] == 0
