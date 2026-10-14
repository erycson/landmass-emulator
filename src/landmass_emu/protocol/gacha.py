"""Item Surpresa no Channel Server: 591 (`NotifyGetGatchaPrize`), resposta ao uso (560).

Layout em re/protocol_full.md §3 (591) e em `channel_dispatch_FUN_1001da60.c` (0x24f): `u16 key`
@0 (índice do item consumido, que o cliente tira da lista), `i32 count` @4, `i32 result` @8
(só com 0 o cliente abre o popup), e os registros `GACHA_PRIZE` a partir de @0xC, de 0x110 bytes.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar

from landmass_emu.domain.gacha import Prize

_HEAD = struct.Struct("<H2xii")  # key @0, pad, count @4, result @8
_PRIZE = struct.Struct("<iii")  # item_id @0, size @4, buy_option @8
_RECORD_SIZE = 0x110
_TEXT_SIZE = _RECORD_SIZE - _PRIZE.size  # descrição UTF-8 NUL-terminada, a partir de @0xC
# O dispatcher lê no máximo 2 prêmios (`while iVar3 < 2`); a abertura dá LD e um prêmio de sorte.
MAX_PRIZES = 2


class CsGachaOp(IntEnum):
    PRIZE_OUT = 591


def _utf8(text: str, size: int) -> bytes:
    raw = text.encode("utf-8")
    if len(raw) >= size:  # corta sem partir um caractere
        raw = raw[: size - 1].decode("utf-8", errors="ignore").encode("utf-8")
    return raw + bytes(size - len(raw))


@dataclass(frozen=True, slots=True)
class CsGachaPrizeOut:
    key: int
    prizes: tuple[Prize, ...]
    result: int = 0
    opcode: ClassVar[int] = CsGachaOp.PRIZE_OUT

    def pack(self) -> bytes:
        if len(self.prizes) > MAX_PRIZES:
            raise ValueError(f"591 leva até {MAX_PRIZES} prêmios, veio {len(self.prizes)}")
        head = _HEAD.pack(self.key, len(self.prizes), self.result)
        records = b"".join(
            _PRIZE.pack(prize.item_id, prize.size, prize.buy_option)
            + _utf8(prize.description, _TEXT_SIZE)
            for prize in self.prizes
        )
        return head + records
