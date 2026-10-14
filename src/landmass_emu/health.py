"""Sonda de saúde do container (D204). Conecta em cada porta de escuta e fecha. O desligamento
mantém os listeners abertos, então a sonda segue verde até o processo sair."""

import asyncio
import contextlib
from collections.abc import Sequence

# Escuta em todas as interfaces é testada pelo loopback da mesma família.
_LOOPBACK = {"0.0.0.0": "127.0.0.1", "::": "::1"}


class HealthProbe:
    def __init__(self, host: str, ports: Sequence[int], timeout: float = 3.0) -> None:
        self._host = _LOOPBACK.get(host, host)
        self._ports = tuple(ports)
        self._timeout = timeout

    async def failures(self) -> list[str]:
        """Uma linha por porta que não aceitou a conexão. Lista vazia é saudável."""
        resultados = await asyncio.gather(*(self._conecta(porta) for porta in self._ports))
        return [falha for falha in resultados if falha is not None]

    async def _conecta(self, porta: int) -> str | None:
        try:
            async with asyncio.timeout(self._timeout):
                _, escrita = await asyncio.open_connection(self._host, porta)
        except (OSError, TimeoutError) as e:
            return f"porta {porta} em {self._host}: {str(e) or type(e).__name__}"
        escrita.close()
        with contextlib.suppress(OSError):
            await escrita.wait_closed()
        return None
