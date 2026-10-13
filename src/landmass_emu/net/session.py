"""Estado de uma conexão. Sem socket: handlers leem o estado e enfileiram corpos."""

import asyncio
from dataclasses import dataclass, field

from landmass_emu.domain.account import Account


@dataclass(slots=True)
class Session:
    peer: str
    account: Account | None = None
    outbox: asyncio.Queue[bytes] = field(default_factory=asyncio.Queue)

    def send(self, body: bytes) -> None:
        """Enfileira corpo com cabeçalho. Só a task de escrita desta conexão grava no socket."""
        self.outbox.put_nowait(body)
