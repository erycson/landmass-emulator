"""Framing TCP do protocolo: `u16 LE tamanho` + corpo (o tamanho não inclui os 2 bytes)."""

import asyncio
import struct

MAX_BODY = 65000
_LEN = struct.Struct("<H")


class FrameError(Exception):
    pass


def encode_frame(body: bytes) -> bytes:
    if len(body) > MAX_BODY:
        raise FrameError(f"corpo grande demais: {len(body)} > {MAX_BODY}")
    return _LEN.pack(len(body)) + body


async def read_frame(reader: asyncio.StreamReader) -> bytes | None:
    """Lê um frame. Retorna None em EOF limpo entre frames."""
    try:
        head = await reader.readexactly(_LEN.size)
    except asyncio.IncompleteReadError as e:
        if e.partial:
            raise FrameError("EOF no meio do cabeçalho do frame") from e
        return None
    (size,) = _LEN.unpack(head)
    if size > MAX_BODY:
        raise FrameError(f"tamanho de frame inválido: {size}")
    return await reader.readexactly(size)
