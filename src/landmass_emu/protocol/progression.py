"""Mensagens de progressão do Channel Server: tutorial (600/601), saldos (900/902) e o registro do
jogador que o 101 carrega. Layouts: re/layouts_f0.md §1.1 e §7.6; re/channel_server.md §3.2.

Offsets são do corpo, depois do cabeçalho `u16`. Os valores de `PlayerRecord` vão para o nó do
jogador: `valor+X = nó+(X+0x10)`.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar

from landmass_emu.domain.inventory import GATE_COUNT


class CsProgressionOp(IntEnum):
    TUTORIAL_CLEAR = 600
    TUTORIAL_CLEAR_OUT = 601
    CHARGE_CASH_OUT = 900
    CHARGE_POINT_OUT = 902


@dataclass(frozen=True, slots=True)
class PlayerRecord:
    """Campos de progressão do registro de 0xa8 bytes do 101 (`LM_PLAYER_INFO`, copiado para o nó).

    @0x28 iTutorialClear (nó+0x38), @0x2c iTotalExp (nó+0x3c), @0x48 iCash (nó+0x58),
    @0x4c iPoint (nó+0x5c). @0x90 e @0xa0 são o id do jogador (chave da lista e do nó).
    Os demais campos ficam zero, exceto nest (@0x20, ucNest) e os sGate (@0x5a + 4·g: siIdx = g e
    bEnable = 1), que vêm do inventário (F5).

    shortcut: nick, clã e estatísticas do 101 seguem zero; o cliente recebe esses campos por outros
    pacotes (151/317/549) ou não os usa no canal. Revisar com o cliente real.
    """

    tutorial_clear: int = 0
    total_exp: int = 0
    cash: int = 0
    point: int = 0
    nest: int = 0
    morat_gates: tuple[int, ...] = ()
    SIZE: ClassVar[int] = 0xA8

    def pack(self, client_guid: int) -> bytes:
        buf = bytearray(self.SIZE)
        for offset, value in (
            (0x28, self.tutorial_clear),
            (0x2C, self.total_exp),
            (0x48, self.cash),
            (0x4C, self.point),
            (0x90, client_guid),
            (0xA0, client_guid),
        ):
            struct.pack_into("<i", buf, offset, value)
        buf[0x20] = self.nest
        for gate in self.morat_gates:
            if not 0 <= gate < GATE_COUNT:
                raise ValueError(f"gate fora da faixa: {gate}")
            struct.pack_into("<hB", buf, 0x5A + 4 * gate, gate, 1)
        return bytes(buf)


@dataclass(frozen=True, slots=True)
class CsTutorialClearIn:
    """TUTORIAL_CLEAR (600), cliente → servidor: `u8 step` @0. Passo 0 a 2 (R-TUT-01)."""

    step: int
    _FORMAT = struct.Struct("<B")

    @classmethod
    def unpack(cls, payload: bytes) -> CsTutorialClearIn:
        (step,) = cls._FORMAT.unpack_from(payload)  # payload curto: struct.error, ignorado
        return cls(step)

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.step)


@dataclass(frozen=True, slots=True)
class CsTutorialClearOut:
    """TUTORIAL_CLEAR_OUT (601): `i32 tutorial_clear` @0 (máscara) e `i32 point` @4 (LD).

    O cliente grava @4 em iPoint. Por isso o servidor responde com o LD atual, nunca com zero.
    O dispatcher lê só @0 e @4 (layouts_f0 §7.6). O `Result` do wrapper (features §1.1) não tem
    offset medido.
    """

    tutorial_clear: int
    point: int
    opcode: ClassVar[int] = CsProgressionOp.TUTORIAL_CLEAR_OUT
    _FORMAT = struct.Struct("<ii")

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.tutorial_clear, self.point)


@dataclass(frozen=True, slots=True)
class CsChargeCashOut:
    """CHARGE_CASH (900), servidor → cliente: `i32 cash` @0 → iCash. Só vale com o nó do jogador."""

    cash: int
    opcode: ClassVar[int] = CsProgressionOp.CHARGE_CASH_OUT
    _FORMAT = struct.Struct("<i")

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.cash)


@dataclass(frozen=True, slots=True)
class CsChargePointOut:
    """CHARGE_POINT (902), servidor → cliente: `i32 point` @0 → iPoint (LD).

    shortcut: 902 é um bloco misto no dispatcher (com NotifyClanInsertPlayer, re/channel_server.md
    §3.2). Só o campo de LD está confirmado; confirmar com o cliente real.
    """

    point: int
    opcode: ClassVar[int] = CsProgressionOp.CHARGE_POINT_OUT
    _FORMAT = struct.Struct("<i")

    def pack(self) -> bytes:
        return self._FORMAT.pack(self.point)
