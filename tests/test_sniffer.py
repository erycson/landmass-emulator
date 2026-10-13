import asyncio
from pathlib import Path

from landmass_emu import sniffer


async def test_grava_bytes_recebidos(tmp_path: Path) -> None:
    [server] = await sniffer.start(tmp_path, ports=[0], host="127.0.0.1")
    port = server.sockets[0].getsockname()[1]
    async with server:
        _, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"\x01\x02hello")
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        for _ in range(50):
            files = list(tmp_path.glob("*.bin"))
            if files and files[0].read_bytes():
                break
            await asyncio.sleep(0.02)
    assert files[0].read_bytes() == b"\x01\x02hello"


def test_hexdump() -> None:
    line = sniffer.hexdump(b"AB\x00")
    assert line.startswith("0000  41 42 00 ")
    assert line.endswith(" AB.")
