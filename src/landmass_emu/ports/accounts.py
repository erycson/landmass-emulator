"""Porta de persistência de contas. Handlers e CLI dependem disto, nunca do SQLAlchemy."""

from typing import Protocol

from landmass_emu.domain.account import Account


class AccountConflict(Exception):
    """Usuário ou nickname já existe."""


class AccountRepository(Protocol):
    async def find_by_user_id(self, user_id: str) -> Account | None: ...

    async def find_by_token_hash(self, token_hash: str) -> Account | None: ...

    async def create(self, user_id: str, nickname: str, token_hash: str) -> Account: ...

    async def set_token_hash(self, account_id: int, token_hash: str) -> None: ...
