"""Canal local de comandos com o LMEmu de cada partida (D254).

O chat de dentro da partida vai ao canal (240 com ` //GAMECHAT`), não ao servidor de jogo; o `/bot`
do dono chega ao emulador e segue por aqui. O LMEmu conecta em `127.0.0.1:<porta>` (`?lmemuctl=` da
URL), manda `hello <chave>` e recebe uma linha por comando. Só escuta em loopback.
"""

import asyncio
import contextlib
import logging

log = logging.getLogger(__name__)

HELLO_TIMEOUT = 10.0


class MatchControl:
    def __init__(self) -> None:
        self._server: asyncio.Server | None = None
        self._links: dict[str, asyncio.StreamWriter] = {}

    async def port(self) -> int:
        """Porta do canal; abre o servidor na primeira chamada."""
        if self._server is None:
            self._server = await asyncio.start_server(self._accept, "127.0.0.1", 0)
        return int(self._server.sockets[0].getsockname()[1])

    async def send(self, key: str, line: str) -> bool:
        """Manda `line` ao LMEmu da partida `key`. Falso se ele não estiver conectado."""
        writer = self._links.get(key)
        if writer is None or writer.is_closing():
            return False
        writer.write(line.encode("latin-1", "replace") + b"\r\n")
        try:
            await writer.drain()
        except ConnectionError:
            return False
        return True

    async def close(self) -> None:
        for writer in list(self._links.values()):
            writer.close()
        self._links.clear()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        key = ""
        try:
            hello = await asyncio.wait_for(reader.readline(), HELLO_TIMEOUT)
            parts = hello.decode("latin-1").split()
            if len(parts) != 2 or parts[0] != "hello":
                log.warning("canal de comandos: saudação inválida %r", hello[:40])
                return
            key = parts[1]
            self._links[key] = writer
            log.info("canal de comandos: partida %s conectada", key)
            while line := await reader.readline():
                log.info("canal de comandos: %s diz %s", key, line.decode("latin-1").rstrip())
        except TimeoutError, ConnectionError:
            pass
        finally:
            if self._links.get(key) is writer:
                del self._links[key]
            writer.close()
            with contextlib.suppress(ConnectionError):
                await writer.wait_closed()
