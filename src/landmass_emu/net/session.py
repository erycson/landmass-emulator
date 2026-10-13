"""Estado de uma conexão. Sem sockets: handlers leem e alteram só este estado."""

from dataclasses import dataclass

from landmass_emu.domain.account import Account


@dataclass(slots=True)
class Session:
    peer: str
    account: Account | None = None
