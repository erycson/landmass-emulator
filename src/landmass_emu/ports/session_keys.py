"""Porta do registro de chaves de sessão: o Message emite (111), o Channel valida (100)."""

from typing import Protocol

from landmass_emu.domain.account import Account


class SessionKeyRegistry(Protocol):
    def issue(self, account: Account) -> str: ...

    def resolve(self, key: str) -> Account | None: ...
