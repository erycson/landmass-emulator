"""Marco 0: escuta as portas dos servidores e grava tudo que o cliente envia, sem responder.

Cada conexão vira um arquivo `captures/<porta>-<timestamp>-<n>.bin` com os bytes crus,
para depois virar fixture de teste do codec.
"""

import asyncio
import itertools
import logging
from collections.abc import Awaitable, Callable, Iterable
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_PORTS = (7312, 7313, 7314)
_conn_ids = itertools.count(1)


def hexdump(data: bytes, width: int = 16) -> str:
    lines = []
    for off in range(0, len(data), width):
        chunk = data[off : off + width]
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{off:04x}  {chunk.hex(' '):<{width * 3}} {text}")
    return "\n".join(lines)


def _handler(
    port: int, out_dir: Path
) -> Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = out_dir / f"{port}-{stamp}-{next(_conn_ids)}.bin"
        log.info("[%d] conexão de %s -> %s", port, peer, path.name)
        try:
            with path.open("wb") as f:
                while data := await reader.read(65536):
                    f.write(data)
                    f.flush()
                    log.info("[%d] %d bytes\n%s", port, len(data), hexdump(data))
        except ConnectionError as e:
            log.info("[%d] conexão caiu: %s", port, e)
        finally:
            writer.close()
            log.info("[%d] %s desconectou", port, peer)

    return handle


async def start(
    out_dir: Path, ports: Iterable[int] = DEFAULT_PORTS, host: str = "0.0.0.0"
) -> list[asyncio.Server]:
    servers = [await asyncio.start_server(_handler(p, out_dir), host, p) for p in ports]
    for s in servers:
        log.info("escutando em %s", s.sockets[0].getsockname())
    return servers


async def run(out_dir: Path, ports: Iterable[int] = DEFAULT_PORTS) -> None:
    servers = await start(out_dir, ports)
    await asyncio.gather(*(s.serve_forever() for s in servers))
