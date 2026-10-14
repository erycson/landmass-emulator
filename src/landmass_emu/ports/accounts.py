"""Porta de persistência de contas. Handlers e CLI dependem disto, nunca do SQLAlchemy."""

from datetime import datetime
from typing import Protocol

from landmass_emu.domain.account import Account


class AccountConflict(Exception):
    """Usuário ou nickname já existe."""


class AccountRepository(Protocol):
    async def find_by_username(self, username: str) -> Account | None: ...

    async def find_by_token_hash(self, token_hash: str) -> Account | None: ...

    async def find_by_nickname(self, nickname: str) -> Account | None: ...

    async def create(self, username: str, nickname: str, token_hash: str) -> Account: ...

    async def set_token_hash(self, account_id: int, token_hash: str) -> None: ...

    async def set_banned_until(self, account_id: int, until: datetime | None) -> None: ...

    async def regular_nest(self, account_id: int) -> int: ...

    async def set_regular(self, account_id: int, nest: int, morat_class: int) -> None: ...
