"""Inventário do Channel Server: 102 (item), 103 (morat), 104 e 105 (morat regular).

Layouts: tools/re/layouts_f0.md §8. Offsets são do corpo (depois do cabeçalho `u16`).

Registro de item (`LM_ITEM_INFO`, 0x34 bytes, dump de LM_Engine): índice `short` @0, `int` @4
(id do catálogo), GUID @8 (`char[37]`, inferido), `u8` apply_flag @0x2d, `int` apply_value @0x30.
O 102 do cliente zera `apply_value` quando o byte @0x35 é não zero; mandamos 0.

Registro de morat (`LM_MORATS_INFO`, 0x5c bytes): mesmo cabeçalho, mais 19 partes `short` de
0x34 a 0x59 (`siMainWeapon`...`siSkinID[2]`); o byte @0x5d é o mesmo sinalizador do 102.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar

# GUID de 36 caracteres mais NUL (`char[37]`). Inferido: ver tools/re/layouts_f0.md §8.
GUID_LENGTH = 36
MORAT_PART_COUNT = 19
# 16 peças em -1: o cliente usa o `DefaultSet` da classe do morat (XInterface, GetWeaponInfo:
# `siMainWeapon >= 0` é índice explícito, `< 0` cai no padrão). Índice 0 não resolve como
# peça. Skins em 0: o kit antigo deixa NULL; -1 para skin não confirmado.
DEFAULT_PARTS = (-1,) * 16 + (0,) * 3


class CsInventoryOp(IntEnum):
    GET_ITEM_OUT = 102
    GET_MORATS_OUT = 103
    SET_REGULAR_OUT = 104
    SET_REGULAR_IN = 105


def _guid_bytes(guid: str) -> bytes:
    raw = guid.encode("ascii")
    if len(raw) != GUID_LENGTH:
        raise ValueError(f"GUID deve ter {GUID_LENGTH} caracteres, veio {len(raw)}")
    return raw


@dataclass(frozen=True, slots=True)
class CsGetItemOut:
    """GET_ITEM_OUT (102): uma unidade do inventário, corpo de 56 bytes (0x38).

    @0 `u16` índice (`siIdx`); @4 `i32` id do catálogo; @8 GUID (`char[37]`); @0x2d `u8`
    apply_flag; @0x30 `i32` apply_value; @0x35 `u8` sinalizador de zerar apply_value (0)."""

    inventory_index: int
    catalog_id: int
    item_guid: str
    apply_flag: int
    apply_value: int
    opcode: ClassVar[int] = CsInventoryOp.GET_ITEM_OUT
    _FIXED = struct.Struct("<Hxxi37sBxxixBxx")

    def pack(self) -> bytes:
        return self._FIXED.pack(
            self.inventory_index,
            self.catalog_id,
            _guid_bytes(self.item_guid),
            self.apply_flag,
            self.apply_value,
            0,
        )


@dataclass(frozen=True, slots=True)
class CsGetMoratsOut:
    """GET_MORATS_OUT (103): um morat, corpo de 96 bytes (0x60).

    A chave de 103 é o gate do morat (`@0`): o cliente grava `sGate[chave].siIdx = chave`
    (inferido, dump de `GetMoratsInfoByGate`). Por isso só morat com gate é enviado.
    Campos iguais ao 102; partes em @0x34..0x59 (`parts`); sinalizador @0x5d."""

    gate_index: int
    catalog_id: int
    item_guid: str
    apply_flag: int
    apply_value: int
    parts: tuple[int, ...] = DEFAULT_PARTS  # 19 valores: 16 peças (índice ou -1) e 3 skins
    opcode: ClassVar[int] = CsInventoryOp.GET_MORATS_OUT
    _FIXED = struct.Struct("<Hxxi37sBxxi19hxxxBxx")

    def pack(self) -> bytes:
        return self._FIXED.pack(
            self.gate_index,
            self.catalog_id,
            _guid_bytes(self.item_guid),
            self.apply_flag,
            self.apply_value,
            *self.parts,
            0,
        )


@dataclass(frozen=True, slots=True)
class CsSetRegularIn:
    """SET_REGULAR (105): `u8 nest` @0 e `u8 morat_class` @1. Ordem de `SetRegular(SelectNest,
    SelectMorats)` (dump de LM_Engine). Faixas são validadas no domínio (`RegularService`)."""

    nest: int
    morat_class: int
    opcode: ClassVar[int] = CsInventoryOp.SET_REGULAR_IN
    _FIXED = struct.Struct("<BB")

    @classmethod
    def unpack(cls, payload: bytes) -> CsSetRegularIn:
        nest, morat_class = cls._FIXED.unpack_from(payload)
        return cls(nest, morat_class)


@dataclass(frozen=True, slots=True)
class CsSetRegularOut:
    """SET_REGULAR_OUT (104): corpo vazio. O dispatcher do cliente não lê corpo (sem resultado)."""

    opcode: ClassVar[int] = CsInventoryOp.SET_REGULAR_OUT

    def pack(self) -> bytes:
        return b""
