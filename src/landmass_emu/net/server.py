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


async def start_service(
    host: str, port: int, *, net_code: int, router: Router, recv_timeout: float
) -> asyncio.Server:
    async def on_connect(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _serve(reader, writer, net_code, router, recv_timeout)

    server = await asyncio.start_server(on_connect, host, port)
    for sock in server.sockets:
        log.info("escutando em %s", sock.getsockname())
    return server


async def _serve(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    net_code: int,
    router: Router,
    recv_timeout: float,
) -> None:
    session = Session(peer=str(writer.get_extra_info("peername")))
    log.info("[%s] conectou", session.peer)
    try:
        await _loop(reader, writer, session, net_code, router, recv_timeout)
    except TimeoutError:
        log.info("[%s] sem tráfego por %s s; desconectando", session.peer, recv_timeout)
    except (EOFError, ConnectionError, FrameError) as e:
        log.info("[%s] conexão encerrada: %s", session.peer, e)
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
        log.info("[%s] desconectou", session.peer)


async def _loop(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
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
            writer.write(encode_frame(pack_header(reply.opcode, net_code) + reply.pack()))
        await writer.drain()


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
