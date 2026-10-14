"""Canal de comandos com o LMEmu (D254), com um cliente TCP no lugar do `LMEmuControl`."""

import asyncio

from landmass_emu.hosting.control import MatchControl


async def test_lmemu_saudado_recebe_o_comando_da_sua_partida() -> None:
    control = MatchControl()
    try:
        porta = await control.port()
        assert await control.send("mabc", "/bot add 7") is False  # ninguém conectado

        reader, writer = await asyncio.open_connection("127.0.0.1", porta)
        writer.write(b"hello mabc\r\n")
        await writer.drain()
        for _ in range(50):
            if await control.send("mabc", "/bot add 7"):
                break
            await asyncio.sleep(0.02)

        assert await asyncio.wait_for(reader.readline(), 5) == b"/bot add 7\r\n"
        assert await control.send("outra", "/bot remove") is False
        writer.close()
    finally:
        await control.close()
