"""Estado de uma conexão. Sem socket: handlers leem o estado e enfileiram corpos."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field

from landmass_emu.domain.account import Account


def _sem_fechamento() -> None:
    """Sessão sem socket (testes): fechar não faz nada."""


@dataclass(slots=True)
class Session:
    peer: str
    account: Account | None = None
    outbox: asyncio.Queue[bytes] = field(default_factory=asyncio.Queue)
    closer: Callable[[], None] = _sem_fechamento

    def send(self, body: bytes) -> None:
        """Enfileira corpo com cabeçalho. Só a task de escrita desta conexão grava no socket."""
        self.outbox.put_nowait(body)

    def close(self) -> None:
        """Fecha o socket. O laço de leitura vê EOF e a queda passa pelo `on_close` do serviço."""
        self.closer()
