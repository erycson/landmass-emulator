"""Layouts do Depósito e do presente (610 a 617) e do Item Surpresa (591), medidos no RE:
`channel_dispatch_FUN_1001da60.c` (casos 0x24f e 0x262 a 0x269) e os wrappers de LM_Engine."""

import struct
from datetime import UTC, datetime

import pytest

from landmass_emu.domain.gacha import Prize
from landmass_emu.domain.inventory import ApplyFlag, ItemUnit
from landmass_emu.handlers.channel.login import item_record
from landmass_emu.protocol.gacha import CsGachaPrizeOut
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


def test_610_pede_a_pagina_em_i32_zero_base() -> None:
    assert CsGetGiftItemIn.unpack(struct.pack("<i", 2)) == CsGetGiftItemIn(2)
    assert CsGetGiftItemIn(0).pack() == bytes(4)


def test_611_vazio_manda_um_registro_zerado_com_count_zero() -> None:
    body = CsGetGiftItemOut(page=0, lines=()).pack()
    assert len(body) == 8 + 0x48
    assert struct.unpack_from("<ii", body, 0) == (0, 0)
    assert body[8:] == bytes(0x48)


def test_611_registro_do_deposito_tem_chave_catalogo_guid_e_prazo() -> None:
    line = GiftLine(key=7, catalog_id=308010006, item_guid="gift-12", buy_option=1)
    body = CsGetGiftItemOut(page=1, lines=(line,)).pack()
    assert len(body) == 8 + 0x48
    assert struct.unpack_from("<ii", body, 0) == (1, 1)
    assert struct.unpack_from("<H", body, 8) == (7,)  # chave u16 @0 do registro
    assert struct.unpack_from("<i", body, 8 + 0x14) == (308010006,)
    assert body[8 + 0x18 : 8 + 0x18 + 7] == b"gift-12"
    assert body[8 + 0x18 + 7] == 0  # NUL-terminado
    assert body[8 + 0x40] == 1  # Buy_Option


def test_611_registros_seguem_o_passo_de_0x48() -> None:
    lines = tuple(GiftLine(key=k, catalog_id=1, item_guid="g", buy_option=0) for k in (1, 2, 3))
    body = CsGetGiftItemOut(page=0, lines=lines).pack()
    assert len(body) == 8 + 3 * 0x48
    assert [struct.unpack_from("<H", body, 8 + i * 0x48) for i in range(3)] == [(1,), (2,), (3,)]


def test_612_pede_a_chave_em_i32() -> None:
    assert CsGiftItemUsedIn.unpack(struct.pack("<i", 9)) == CsGiftItemUsedIn(9)


def test_613_registro_resultado_e_chave_nos_offsets_do_dispatcher() -> None:
    unit = ItemUnit(
        account_id=1,
        inventory_index=5,
        catalog_id=308010006,
        item_guid="a" * 36,
        apply_flag=ApplyFlag.REALTIME,
        apply_value=None,
        expires_at=datetime(2026, 11, 1, tzinfo=UTC),
    )
    body = CsGiftItemUsedOut(result=0, key=9, item=item_record(unit)).pack()
    assert len(body) == 0x3C
    assert body[:0x34] == item_record(unit).pack()[:0x34]
    assert struct.unpack_from("<H", body, 0) == (5,)  # índice do item @0
    assert struct.unpack_from("<i", body, 0x34) == (0,)  # resultado
    assert struct.unpack_from("<i", body, 0x38) == (9,)  # chave do Depósito


def test_613_recusa_manda_registro_zerado_e_resultado_negativo() -> None:
    body = CsGiftItemUsedOut(result=-4071, key=3).pack()
    assert body[:0x34] == bytes(0x34)
    assert struct.unpack_from("<ii", body, 0x34) == (-4071, 3)


def test_615_decodifica_catalogo_moeda_opcao_e_nick() -> None:
    raw = struct.pack("<iBB18s", 201020001, 1, 2, "Bia".encode("ascii").ljust(18, b"\x00"))
    req = CsItemGiftIn.unpack(raw)
    assert (req.catalog_id, req.point, req.option, req.nick) == (201020001, True, 2, "Bia")


def test_615_nick_sem_nul_usa_os_18_bytes() -> None:
    raw = struct.pack("<iBB18s", 1, 0, 0, b"x" * 18)
    assert CsItemGiftIn.unpack(raw).nick == "x" * 18


def test_616_leva_resultado_e_saldos_do_remetente() -> None:
    assert CsItemGiftOut(0, cash=500, point=700).pack() == struct.pack("<iii", 0, 500, 700)
    assert CsItemGiftOut(-4056).pack() == struct.pack("<iii", -4056, 0, 0)


def test_617_nao_tem_corpo() -> None:
    assert CsGiftNoticeOut().pack() == b""


def test_591_cabecalho_de_12_e_registro_de_0x110() -> None:
    prizes = (Prize(0, 1, 0, "5000 LD"), Prize(307010002, 1, 1, "Pintura: Desert (7 dias)"))
    body = CsGachaPrizeOut(key=4, prizes=prizes).pack()
    assert len(body) == 0xC + 2 * 0x110
    assert struct.unpack_from("<H", body, 0) == (4,)  # chave: índice do item consumido
    assert struct.unpack_from("<ii", body, 4) == (2, 0)  # quantidade e resultado
    assert struct.unpack_from("<iii", body, 0xC) == (0, 1, 0)
    assert body[0xC + 12 : 0xC + 12 + 7] == "5000 LD".encode("ascii")
    second = 0xC + 0x110
    assert struct.unpack_from("<iii", body, second) == (307010002, 1, 1)
    assert body[second + 12 :].split(b"\x00", 1)[0].decode("utf-8") == "Pintura: Desert (7 dias)"


def test_591_descricao_longa_corta_em_utf8_com_nul() -> None:
    longa = "á" * 300
    body = CsGachaPrizeOut(key=1, prizes=(Prize(0, 1, 0, longa),)).pack()
    texto = body[0xC + 12 : 0xC + 0x110]
    assert len(texto) == 0x110 - 12
    assert texto[-1] == 0
    assert texto.split(b"\x00", 1)[0].decode("utf-8") == "á" * 129


def test_591_nao_leva_mais_de_dois_premios() -> None:
    prizes = tuple(Prize(0, 1, 0, "x") for _ in range(3))
    with pytest.raises(ValueError, match="até 2"):
        CsGachaPrizeOut(key=1, prizes=prizes).pack()
