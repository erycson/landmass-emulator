"""Loja do Channel Server: compra (550) e resultados (551 para item, 552 para morat).

Layouts em tools/re/protocol_full.md §3.1 (550) e §3.2 (551, 552); tools/re/layouts_f0.md §7.6.
Offsets são do
corpo, depois do cabeçalho `u16`. O registro da unidade vem dos codecs 102 e 103 (`CsGetItemOut`,
`CsGetMoratsOut`): o 551 usa os primeiros 0x34 bytes do 102, e o 552, os primeiros 0x5c do 103.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar

from landmass_emu.protocol.inventory import CsGetItemOut, CsGetMoratsOut

# Registro sem o sinalizador do fim do corpo (@0x35 no 102, @0x5d no 103): não entra no 551/552.
_ITEM_RECORD_SIZE = 0x34
_MORAT_RECORD_SIZE = 0x5C
# Saldos e resultado, na mesma ordem nos dois (551: @0x38, @0x3c, @0x40; 552: @0x5c, @0x60, @0x64).
_TAIL = struct.Struct("<iii")


class CsShopOp(IntEnum):
    ITEM_BUY_IN = 550
    ITEM_BUY_OUT = 551
    MORATS_BUY_OUT = 552


@dataclass(frozen=True, slots=True)
class CsItemBuyIn:
    """ITEM_BUY (550), cliente → servidor: `i32 id` @0; `u8 bPoint` @4 (1 = LD, 0 = Cash); `u8
    nBuyOption` @5 (índice do prazo, 0 a 3). Os demais bytes do corpo de 12 são zero."""

    catalog_id: int
    point: bool
    option: int
    opcode: ClassVar[int] = CsShopOp.ITEM_BUY_IN
    _FORMAT = struct.Struct("<iBB")

    @classmethod
    def unpack(cls, payload: bytes) -> CsItemBuyIn:
        catalog_id, point, option = cls._FORMAT.unpack_from(payload)  # curto: struct.error
        return cls(catalog_id, bool(point), option)

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.catalog_id, int(self.point), self.option) + bytes(6)


@dataclass(frozen=True, slots=True)
class CsItemBuyOut:
    """ITEM_BUY_OUT (551), servidor → cliente: registro de item @0..0x33 (chave `u16` @0), pad até
    0x38, `i32 cash` @0x38, `i32 point` @0x3c, `i32 result` @0x40. Corpo de 0x44.

    O cliente só aplica o registro e os saldos com `result` 0 (dispatcher L696–715). Recusa vai sem
    registro e com saldos zero.
    """

    result: int
    cash: int
    point: int
    item: CsGetItemOut | None = None
    opcode: ClassVar[int] = CsShopOp.ITEM_BUY_OUT

    def pack(self) -> bytes:
        record = self.item.pack()[:_ITEM_RECORD_SIZE] if self.item else bytes(_ITEM_RECORD_SIZE)
        return record + bytes(4) + _TAIL.pack(self.cash, self.point, self.result)


@dataclass(frozen=True, slots=True)
class CsMoratsBuyOut:
    """MORATS_BUY_OUT (552), servidor → cliente: registro de morat @0..0x5b (chave `u16` @0 = gate),
    `i32 cash` @0x5c, `i32 point` @0x60, `i32 result` @0x64. Corpo de 0x68.

    Mesma regra de saldo do 551 (dispatcher L740–744, só com result 0).
    """

    result: int
    cash: int
    point: int
    morat: CsGetMoratsOut | None = None
    opcode: ClassVar[int] = CsShopOp.MORATS_BUY_OUT

    def pack(self) -> bytes:
        record = self.morat.pack()[:_MORAT_RECORD_SIZE] if self.morat else bytes(_MORAT_RECORD_SIZE)
        return record + _TAIL.pack(self.cash, self.point, self.result)
