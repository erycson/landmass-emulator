"""Cabeçalho do corpo: `u16 LE = (opcode << 5) | net_code`."""

import struct
from typing import NamedTuple

HEADER = struct.Struct("<H")
NET_CODE_MASK = 0x1F

MESSAGE_NET_CODE = 13
CHANNEL_NET_CODE = 14


class Header(NamedTuple):
    opcode: int
    net_code: int


def pack_header(opcode: int, net_code: int) -> bytes:
    if not 0 <= net_code <= NET_CODE_MASK or not 0 <= opcode < (1 << 11):
        raise ValueError(f"cabeçalho fora da faixa: opcode={opcode} net_code={net_code}")
    return HEADER.pack((opcode << 5) | net_code)


def unpack_header(body: bytes) -> tuple[Header, bytes]:
    """Separa o cabeçalho do payload."""
    if len(body) < HEADER.size:
        raise ValueError("corpo menor que o cabeçalho")
    (raw,) = HEADER.unpack_from(body)
    return Header(raw >> 5, raw & NET_CODE_MASK), body[HEADER.size :]
