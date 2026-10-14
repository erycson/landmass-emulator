"""Depósito e presente no Channel Server: 610 e 611 (listagem), 612 e 613 (resgate), 615 e 616
(envio) e 617 (aviso ao destinatário). Layouts em tools/re/protocol_full.md §3 (610 a 617) e nos
dispatchers de `tools/re/LM_Engine.dll/channel_dispatch_FUN_1001da60.c` (casos 0x262 a 0x269).
Offsets são
do corpo, depois do cabeçalho `u16`.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar

from landmass_emu.protocol.inventory import CsGetItemOut
from landmass_emu.protocol.message import cfield, cstr

_ITEM_RECORD_SIZE = 0x34  # registro de item (102) sem o sinalizador do fim do corpo
_LIST_RECORD_SIZE = 0x48  # registro do Depósito (611), um por pendente
_NICK_SIZE = 18


class CsGiftOp(IntEnum):
    GET_GIFT_ITEM_IN = 610
    GET_GIFT_ITEM_OUT = 611
    GIFT_ITEM_USED_IN = 612
    GIFT_ITEM_USED_OUT = 613
    ITEM_GIFT_IN = 615
    ITEM_GIFT_OUT = 616
    GET_GIFT_OUT = 617


@dataclass(frozen=True, slots=True)
class CsGetGiftItemIn:
    """GET_GIFT_ITEM (610), cliente → servidor: `i32 page` @0, 0 a n (a tela começa em 0)."""

    page: int
    opcode: ClassVar[int] = CsGiftOp.GET_GIFT_ITEM_IN
    _FORMAT = struct.Struct("<i")

    @classmethod
    def unpack(cls, payload: bytes) -> CsGetGiftItemIn:
        (page,) = cls._FORMAT.unpack_from(payload)  # curto: struct.error
        return cls(page)

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.page)


@dataclass(frozen=True, slots=True)
class GiftLine:
    """Registro de 0x48 do Depósito: `u16 key` @0 (chave do 612), `short siIdx` @0x10 (0, inferido),
    `i32 catalog` @0x14, GUID ANSI NUL-terminado @0x18, `u8 Buy_Option` @0x40 (índice do prazo),
    e o nick de quem enviou @0x44 (só 4 bytes: vai vazio; ver 07-progression §5.6)."""

    key: int
    catalog_id: int
    item_guid: str
    buy_option: int

    def pack(self) -> bytes:
        body = bytearray(_LIST_RECORD_SIZE)
        struct.pack_into("<H", body, 0, self.key)
        struct.pack_into("<i", body, 0x14, self.catalog_id)
        body[0x18:0x40] = cfield(self.item_guid, 0x28)
        body[0x40] = self.buy_option
        return bytes(body)


@dataclass(frozen=True, slots=True)
class CsGetGiftItemOut:
    """GET_GIFT_ITEM_OUT (611): `i32 page` @0, `i32 count` @4 (registros desta página), e os
    registros a partir de @8. O dispatcher lê sempre um registro: com count 0, manda um zerado."""

    page: int
    lines: tuple[GiftLine, ...]
    opcode: ClassVar[int] = CsGiftOp.GET_GIFT_ITEM_OUT

    def pack(self) -> bytes:
        records = b"".join(line.pack() for line in self.lines) or bytes(_LIST_RECORD_SIZE)
        return struct.pack("<ii", self.page, len(self.lines)) + records


@dataclass(frozen=True, slots=True)
class CsGiftItemUsedIn:
    """GIFT_ITEM_USED (612), cliente → servidor: `i32 key` @0 (a chave do registro do 611)."""

    key: int
    opcode: ClassVar[int] = CsGiftOp.GIFT_ITEM_USED_IN
    _FORMAT = struct.Struct("<i")

    @classmethod
    def unpack(cls, payload: bytes) -> CsGiftItemUsedIn:
        (key,) = cls._FORMAT.unpack_from(payload)  # curto: struct.error
        return cls(key)

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.key)


@dataclass(frozen=True, slots=True)
class CsGiftItemUsedOut:
    """GIFT_ITEM_USED_OUT (613): registro do item @0..0x33 (o 102 sem o sinalizador), `i32 result`
    @0x34 e `i32 key` @0x38. Corpo de 0x3c. O cliente só insere o item com `result` 0 e tira a
    chave `key` do Depósito."""

    result: int
    key: int
    item: CsGetItemOut | None = None
    opcode: ClassVar[int] = CsGiftOp.GIFT_ITEM_USED_OUT
    _TAIL = struct.Struct("<ii")

    def pack(self) -> bytes:
        record = self.item.pack()[:_ITEM_RECORD_SIZE] if self.item else bytes(_ITEM_RECORD_SIZE)
        return record + self._TAIL.pack(self.result, self.key)


@dataclass(frozen=True, slots=True)
class CsItemGiftIn:
    """ITEM_GIFT (615), cliente → servidor: `i32 catalog` @0; `u8 bPoint` @4 (1 = LD, 0 = Cash);
    `u8 option` @5 (prazo, 0 a 3); `char nick[18]` @6, NUL-terminado. Corpo de 24."""

    catalog_id: int
    point: bool
    option: int
    nick: str
    opcode: ClassVar[int] = CsGiftOp.ITEM_GIFT_IN
    _FORMAT = struct.Struct("<iBB18s")

    @classmethod
    def unpack(cls, payload: bytes) -> CsItemGiftIn:
        catalog_id, point, option, raw = cls._FORMAT.unpack_from(payload)  # curto: struct.error
        return cls(catalog_id, bool(point), option, cstr(raw[:_NICK_SIZE]))


@dataclass(frozen=True, slots=True)
class CsItemGiftOut:
    """ITEM_GIFT_OUT (616), servidor → cliente: `i32 result` @0; com 0, `i32 cash` @4 e `i32 point`
    @8 (saldos do remetente). Refusa com um código negativo (`NotifyItemGift`, XInterface)."""

    result: int
    cash: int = 0
    point: int = 0
    opcode: ClassVar[int] = CsGiftOp.ITEM_GIFT_OUT
    _FORMAT = struct.Struct("<iii")

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.result, self.cash, self.point)


@dataclass(frozen=True, slots=True)
class CsGiftNoticeOut:
    """GET_GIFT_OUT (617), servidor → destinatário: sem corpo (`NotifyGetGift` não lê campos)."""

    opcode: ClassVar[int] = CsGiftOp.GET_GIFT_OUT

    def pack(self) -> bytes:
        return b""


__all__ = [
    "CsGetGiftItemIn",
    "CsGetGiftItemOut",
    "CsGiftItemUsedIn",
    "CsGiftItemUsedOut",
    "CsGiftNoticeOut",
    "CsGiftOp",
    "CsItemGiftIn",
    "CsItemGiftOut",
    "GiftLine",
]
