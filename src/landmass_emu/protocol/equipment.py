"""Equipar, desequipar, destruir e estender (F6, F7) no Channel Server: 554 a 585.

Requisições (cliente → servidor): 555, 560, 570, 580. Respostas: 554, 556, 557, 559, 561, 562, 572,
582, 585. Offsets são do corpo, depois do cabeçalho `u16`. Fonte: re/protocol_full.md §3.1 e §3.2;
dispatcher `re/LM_Engine.dll/channel_dispatch_FUN_1001da60.c` (L110–170, L776–802, L2490–2528,
L2616–2633, L2634–2704). Cada resposta só aplica o estado no cliente com `result` 0; por isso a
recusa vai com o opcode da resposta e `result` ≠ 0, sem registro.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar

from landmass_emu.protocol.inventory import CsGetItemOut

# Registro de item sem o sinalizador do fim do corpo: 0x34 bytes, como no 102 e no 551.
_ITEM_RECORD_SIZE = 0x34


class CsEquipOp(IntEnum):
    ITEM_USED_SYSTEM_OUT = 554
    ITEM_DESTROY_IN = 555
    ITEM_DESTROY_OUT = 556
    MORATS_DESTROY_OUT = 557
    ITEM_DESTROY_SYSTEM_OUT = 559
    ITEM_USED_IN = 560
    ITEM_USED_REFUSED_OUT = 561
    ITEM_USED_PIECE_OUT = 562
    SKIN_MOUNTED_OUT = 565
    ITEM_CONSUMED_OUT = 568
    CHANGE_NEST_OUT = 569
    ITEM_UNUSED_IN = 570
    ITEM_UNUSED_PIECE_OUT = 572
    SKIN_UNUSED_OUT = 573
    CHANGE_MORAT_CLASS_OUT = 590
    ITEM_EXTEND_IN = 580
    ITEM_EXTEND_OUT = 582
    ITEM_ENDTIME_OUT = 585


@dataclass(frozen=True, slots=True)
class CsItemDestroyIn:
    """ITEM_DESTROY (555): `i32 id` @0; `u16 index` @4 (o gate, no caso de morat)."""

    catalog_id: int
    index: int
    opcode: ClassVar[int] = CsEquipOp.ITEM_DESTROY_IN
    _FORMAT = struct.Struct("<iH")

    @classmethod
    def unpack(cls, payload: bytes) -> CsItemDestroyIn:
        catalog_id, index = cls._FORMAT.unpack_from(payload)  # curto: struct.error
        return cls(catalog_id, index)


@dataclass(frozen=True, slots=True)
class CsItemUsedIn:
    """ITEM_USED (560): `u16 index` @0; `u16 gate` @2; `i32 value` @4 (0 no uso comum; o valor de
    ItemUsedByValue, que o F6 não cobre, vem aqui)."""

    index: int
    gate: int
    value: int
    opcode: ClassVar[int] = CsEquipOp.ITEM_USED_IN
    _FORMAT = struct.Struct("<HHi")

    @classmethod
    def unpack(cls, payload: bytes) -> CsItemUsedIn:
        index, gate, value = cls._FORMAT.unpack_from(payload)  # curto: struct.error
        return cls(index, gate, value)


@dataclass(frozen=True, slots=True)
class CsItemUnusedIn:
    """ITEM_UNUSED (570): `u16 index` @0; `u16 gate` @2. Desmonta a peça do gate."""

    index: int
    gate: int
    opcode: ClassVar[int] = CsEquipOp.ITEM_UNUSED_IN
    _FORMAT = struct.Struct("<HH")

    @classmethod
    def unpack(cls, payload: bytes) -> CsItemUnusedIn:
        index, gate = cls._FORMAT.unpack_from(payload)  # curto: struct.error
        return cls(index, gate)


@dataclass(frozen=True, slots=True)
class CsItemExtendIn:
    """ITEM_EXTEND (580): `i32 id` @0; `u16 index` @4; `u8 point` @6 (1 = LD); `u8 option` @7."""

    catalog_id: int
    index: int
    point: bool
    option: int
    opcode: ClassVar[int] = CsEquipOp.ITEM_EXTEND_IN
    _FORMAT = struct.Struct("<iHBB")

    @classmethod
    def unpack(cls, payload: bytes) -> CsItemExtendIn:
        catalog_id, index, point, option = cls._FORMAT.unpack_from(payload)  # curto: struct.error
        return cls(catalog_id, index, bool(point), option)


@dataclass(frozen=True, slots=True)
class CsItemUsedSystemOut:
    """554: registro do item de sistema (0x34 bytes, como o 102), `u16 slot` @0x34 (0 a 9, o
    `sEventSlot` do cliente) e `i32 result` @0x38. O cliente grava o índice do item no slot."""

    item: CsGetItemOut
    slot: int
    result: int
    opcode: ClassVar[int] = CsEquipOp.ITEM_USED_SYSTEM_OUT
    _TAIL = struct.Struct("<Hxxi")

    def pack(self) -> bytes:
        return self.item.pack()[:_ITEM_RECORD_SIZE] + self._TAIL.pack(self.slot, self.result)


@dataclass(frozen=True, slots=True)
class CsItemUsedRefusedOut:
    """561: só `i32 result` @8. Recusa de ItemUsed (560), sem chave nem registro."""

    result: int
    opcode: ClassVar[int] = CsEquipOp.ITEM_USED_REFUSED_OUT

    def pack(self) -> bytes:
        return struct.pack("<8xi", self.result)


@dataclass(frozen=True, slots=True)
class CsItemUsedPieceOut:
    """562: `u16 gate` @0; `u16 index` @2 (o item montado, ou 0 na recusa); `u16 slot` @6 (0 a 15,
    `SLOT_NAMES`); `i32 result` @8. Com result 0, o cliente grava `index` na peça `slot` do gate."""

    gate: int
    index: int
    slot: int
    result: int
    opcode: ClassVar[int] = CsEquipOp.ITEM_USED_PIECE_OUT
    _FORMAT = struct.Struct("<HHxxHi")

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.gate, self.index, self.slot, self.result)


@dataclass(frozen=True, slots=True)
class CsItemUnusedPieceOut:
    """572: `u16 gate` @0; `u16 slot` @4 (0 a 15); `i32 result` @8. Com result 0, limpa a peça."""

    gate: int
    slot: int
    result: int
    opcode: ClassVar[int] = CsEquipOp.ITEM_UNUSED_PIECE_OUT
    _FORMAT = struct.Struct("<HxxHxxi")

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.gate, self.slot, self.result)


@dataclass(frozen=True, slots=True)
class CsSkinMountedOut:
    """565: `u16 gate` @0 (chave do morat); `u16 value` @2 (índice da pintura, vai para `siSkinID`);
    `u16 slot` @4 (`k` da skin, 0 a 2); `i32 result` @8. Com result 0, o cliente grava `value` em
    `siSkinID[k]` do morat (inferido: o `k` da pintura é sempre 0, D136)."""

    gate: int
    value: int
    slot: int
    result: int
    opcode: ClassVar[int] = CsEquipOp.SKIN_MOUNTED_OUT
    _FORMAT = struct.Struct("<HHHxxi")

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.gate, self.value, self.slot, self.result)


@dataclass(frozen=True, slots=True)
class CsSkinUnusedOut:
    """573: `u16 gate` @0; `u16 slot` @4 (`k` da skin); `i32 result` @8. Com result 0, o cliente
    limpa `siSkinID[k]` do morat (inferido: o 573 grava 0xffff no índice)."""

    gate: int
    slot: int
    result: int
    opcode: ClassVar[int] = CsEquipOp.SKIN_UNUSED_OUT
    _FORMAT = struct.Struct("<HxxHxxi")

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.gate, self.slot, self.result)


@dataclass(frozen=True, slots=True)
class CsItemConsumedOut:
    """568: `u16 index` @0 (o item consumido, que o cliente tira da lista); `i32 result` @4. Com
    result 0, o cliente remove a unidade e mostra a mensagem 101 (`NotifyItemUsed`)."""

    index: int
    result: int
    opcode: ClassVar[int] = CsEquipOp.ITEM_CONSUMED_OUT
    _FORMAT = struct.Struct("<Hxxi")

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.index, self.result)


@dataclass(frozen=True, slots=True)
class CsChangeNestOut:
    """569: `u16 index` @0 (o Alistar, que o cliente remove); `u8 nest` @2 (vai para o nó do jogador
    +0x30, inferido); `i32 result` @4. Com result 0, o cliente troca o nest regular."""

    index: int
    nest: int
    result: int
    opcode: ClassVar[int] = CsEquipOp.CHANGE_NEST_OUT
    _FORMAT = struct.Struct("<HBxi")

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.index, self.nest, self.result)


@dataclass(frozen=True, slots=True)
class CsChangeMoratClassOut:
    """590: `u16 index` @0 (a Troca de Função, que o cliente remove); `u8 morat_class` @2 (vai para
    o nó do morat +0x98, inferido); `i32 result` @4. Sem envelope de erro, o cliente aplica: a
    recusa vai por 561 (o 590 não confere `result`)."""

    index: int
    morat_class: int
    result: int
    opcode: ClassVar[int] = CsEquipOp.CHANGE_MORAT_CLASS_OUT
    _FORMAT = struct.Struct("<HBxi")

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.index, self.morat_class, self.result)


@dataclass(frozen=True, slots=True)
class CsItemDestroyOut:
    """556: `u16 index` @0; `u16 gate` @2 (morat do item, se montado); `u8 mounted` @4; `i32
    result` @8. Com result 0 e `mounted`, o cliente tira o item da peça do gate."""

    index: int
    gate: int
    mounted: bool
    result: int
    opcode: ClassVar[int] = CsEquipOp.ITEM_DESTROY_OUT
    _FORMAT = struct.Struct("<HHBxxxi")

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.index, self.gate, int(self.mounted), self.result)


@dataclass(frozen=True, slots=True)
class CsItemDestroySystemOut:
    """559: como o 556, com `u16 slot` @2 em vez do gate: o slot de sistema (0 a 9) que o cliente
    limpa em `sEventSlot`."""

    index: int
    slot: int
    result: int
    opcode: ClassVar[int] = CsEquipOp.ITEM_DESTROY_SYSTEM_OUT
    _FORMAT = struct.Struct("<HHBxxxi")

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.index, self.slot, 1, self.result)


@dataclass(frozen=True, slots=True)
class CsMoratsDestroyOut:
    """557: `u16 gate` @0; `i32 result` @4. Com result 0, o cliente apaga o morat do gate."""

    gate: int
    result: int
    opcode: ClassVar[int] = CsEquipOp.MORATS_DESTROY_OUT
    _FORMAT = struct.Struct("<Hxxi")

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.gate, self.result)


@dataclass(frozen=True, slots=True)
class CsItemExtendOut:
    """582: `u16 index` @0; `i32 apply` @4 (o novo `apply_value`, o fim em segundos Unix para
    REALTIME); `i32 cash` @8; `i32 point` @0xc (LD); `i32 result` @0x10. Com result 0, o cliente
    grava o prazo e os saldos."""

    index: int
    apply_value: int
    cash: int
    point: int
    result: int
    opcode: ClassVar[int] = CsEquipOp.ITEM_EXTEND_OUT
    _FORMAT = struct.Struct("<Hxxiiii")

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.index, self.apply_value, self.cash, self.point, self.result)


@dataclass(frozen=True, slots=True)
class CsItemEndtimeOut:
    """585: `u8 premium` @0 (sempre 0 aqui; o cliente não lê); `u8 item` @1 (1 = item, 0 = morat);
    `u16 index` @2. Avisa que o item venceu: o cliente abre a renovação."""

    index: int
    opcode: ClassVar[int] = CsEquipOp.ITEM_ENDTIME_OUT
    _FORMAT = struct.Struct("<BBH")

    def pack(self) -> bytes:
        return self._FORMAT.pack(0, 1, self.index)
