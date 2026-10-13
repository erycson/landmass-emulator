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


async def start_service(
    host: str,
    port: int,
    *,
    net_code: int,
    router: Router,
    recv_timeout: float,
    on_close: Callable[[Session], None] | None = None,
    heartbeat: Reply | None = None,
    heartbeat_every: float = 10.0,
) -> asyncio.Server:
    """`on_close` roda ao fim da conexão (presença). `heartbeat`, se dado, é enviado a cada
    `heartbeat_every` segundos; o servidor nunca responde a um heartbeat do cliente."""

    async def on_connect(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _serve(
            reader,
            writer,
            net_code=net_code,
            router=router,
            recv_timeout=recv_timeout,
            on_close=on_close,
            heartbeat=heartbeat,
            heartbeat_every=heartbeat_every,
        )

    server = await asyncio.start_server(on_connect, host, port)
    for sock in server.sockets:
        log.info("escutando em %s", sock.getsockname())
    return server


async def _serve(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *,
    net_code: int,
    router: Router,
    recv_timeout: float,
    on_close: Callable[[Session], None] | None,
    heartbeat: Reply | None,
    heartbeat_every: float,
) -> None:
    session = Session(peer=str(writer.get_extra_info("peername")))
    log.info("[%s] conectou", session.peer)
    tasks = [asyncio.create_task(_pump(session, writer))]
    if heartbeat is not None:
        tasks.append(
            asyncio.create_task(_beat(session, reply_body(heartbeat, net_code), heartbeat_every))
        )
    try:
        await _loop(reader, session, net_code, router, recv_timeout)
    except TimeoutError:
        log.info("[%s] sem tráfego por %s s; desconectando", session.peer, recv_timeout)
    except (EOFError, ConnectionError, FrameError) as e:
        log.info("[%s] conexão encerrada: %s", session.peer, e)
    finally:
        if on_close is not None:
            on_close(session)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
        log.info("[%s] desconectou", session.peer)


async def _pump(session: Session, writer: asyncio.StreamWriter) -> None:
    """Única task que escreve no socket desta conexão. As demais enfileiram em `session.outbox`."""
    try:
        while True:
            body = await session.outbox.get()
            writer.write(encode_frame(body))
            await writer.drain()
    except OSError:
        writer.close()  # _loop vê EOF e encerra a conexão


async def _beat(session: Session, body: bytes, every: float) -> None:
    while True:
        await asyncio.sleep(every)
        session.send(body)


async def _loop(
    reader: asyncio.StreamReader,
    session: Session,
    net_code: int,
    router: Router,
    recv_timeout: float,
) -> None:
    while True:
        async with asyncio.timeout(recv_timeout):
            body = await read_frame(reader)
        if body is None:
            return
        for reply in await _dispatch(session, body, net_code, router):
            session.send(reply_body(reply, net_code))


async def _dispatch(
    session: Session, body: bytes, net_code: int, router: Router
) -> Sequence[Reply]:
    try:
        header, payload = unpack_header(body)
    except ValueError:
        log.warning("[%s] corpo menor que o cabeçalho; descartado", session.peer)
        return []
    if header.net_code != net_code:
        log.warning(
            "[%s] net_code %d nesta porta (esperado %d); descartado",
            session.peer,
            header.net_code,
            net_code,
        )
        return []
    handler = router.get(header.opcode)
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
