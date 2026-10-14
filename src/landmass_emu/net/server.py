"""Servidor de um serviço: framing, roteamento opcode → handler, envio de respostas e timeout."""

import asyncio
import contextlib
import logging
import struct
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import ClassVar, Protocol

from landmass_emu.net.framing import FrameError, encode_frame, read_frame
from landmass_emu.net.session import Session
from landmass_emu.protocol.header import pack_header, unpack_header
from landmass_emu.sniffer import hexdump

log = logging.getLogger(__name__)


class Reply(Protocol):
    """Resposta pronta para envio. O opcode é o do próprio tipo (pedido + 1)."""

    opcode: ClassVar[int]

    def pack(self) -> bytes: ...


Handler = Callable[[Session, bytes], Awaitable[Sequence[Reply]]]
Router = Mapping[int, Handler]


def reply_body(reply: Reply, net_code: int) -> bytes:
    """Corpo com cabeçalho, pronto para `Session.send`. O framing `u16` é feito na escrita."""
    return pack_header(reply.opcode, net_code) + reply.pack()


class Service:
    """Um serviço TCP. `heartbeat`, se dado, é enviado a cada `heartbeat_every` segundos; o servidor
    nunca responde a um heartbeat do cliente. `on_close` roda ao fim da conexão (presença)."""

    def __init__(
        self,
        *,
        net_code: int,
        router: Router,
        recv_timeout: float,
        on_close: Callable[[Session], None] | None = None,
        heartbeat: Reply | None = None,
        heartbeat_every: float = 10.0,
        accepting: Callable[[], bool] | None = None,
    ) -> None:
        self._net_code = net_code
        self._router = router
        self._recv_timeout = recv_timeout
        self._on_close = on_close
        self._heartbeat = heartbeat
        self._heartbeat_every = heartbeat_every
        # Falso: a conexão nova é fechada logo depois do accept. O socket continua aberto, para o
        # health por TCP seguir verde durante o desligamento (D204).
        self._accepting = accepting

    async def start(self, host: str, port: int) -> asyncio.Server:
        server = await asyncio.start_server(self._serve, host, port)
        for sock in server.sockets:
            log.info("escutando em %s", sock.getsockname())
        return server

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        if self._accepting is not None and not self._accepting():
            log.info(
                "[%s] conexão recusada: desligamento em curso", writer.get_extra_info("peername")
            )
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()
            return
        session = Session(peer=str(writer.get_extra_info("peername")), closer=writer.close)
        log.info("[%s] conectou", session.peer)
        tasks = [asyncio.create_task(self._pump(session, writer))]
        if self._heartbeat is not None:
            body = reply_body(self._heartbeat, self._net_code)
            tasks.append(asyncio.create_task(self._beat(session, body, self._heartbeat_every)))
        try:
            await self._loop(reader, session)
        except TimeoutError:
            log.info("[%s] sem tráfego por %s s; desconectando", session.peer, self._recv_timeout)
        except (EOFError, ConnectionError, FrameError) as e:
            log.info("[%s] conexão encerrada: %s", session.peer, e)
        finally:
            if self._on_close is not None:
                self._on_close(session)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()
            log.info("[%s] desconectou", session.peer)

    @staticmethod
    async def _pump(session: Session, writer: asyncio.StreamWriter) -> None:
        """Única task que escreve no socket da conexão. As demais enfileiram em `outbox`."""
        try:
            while True:
                body = await session.outbox.get()
                writer.write(encode_frame(body))
                await writer.drain()
        except OSError:
            writer.close()  # _loop vê EOF e encerra a conexão

    @staticmethod
    async def _beat(session: Session, body: bytes, every: float) -> None:
        while True:
            await asyncio.sleep(every)
            session.send(body)

    async def _loop(self, reader: asyncio.StreamReader, session: Session) -> None:
        while True:
            async with asyncio.timeout(self._recv_timeout):
                body = await read_frame(reader)
            if body is None:
                return
            for reply in await self._dispatch(session, body):
                session.send(reply_body(reply, self._net_code))

    async def _dispatch(self, session: Session, body: bytes) -> Sequence[Reply]:
        try:
            header, payload = unpack_header(body)
        except ValueError:
            log.warning("[%s] corpo menor que o cabeçalho; descartado", session.peer)
            return []
        if header.net_code != self._net_code:
            log.warning(
                "[%s] net_code %d nesta porta (esperado %d); descartado",
                session.peer,
                header.net_code,
                self._net_code,
            )
            return []
        handler = self._router.get(header.opcode)
        if handler is None:
            log.warning(
                "[%s] opcode %d sem handler; ignorado\n%s",
                session.peer,
                header.opcode,
                hexdump(payload),
            )
            return []
        log.debug("[%s] opcode %d", session.peer, header.opcode)
        try:
            return await handler(session, payload)
        except (ValueError, struct.error) as e:
            log.warning("[%s] opcode %d com payload inválido: %s", session.peer, header.opcode, e)
            return []
