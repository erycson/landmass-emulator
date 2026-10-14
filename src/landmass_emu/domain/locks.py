"""Trava de economia por conta (07-progression §2, princípio 6). Compra, uso, destruição e extensão
usam a mesma trava, para que dois pedidos da mesma conta não disputem o saldo ao mesmo tempo."""

import asyncio


class AccountLocks:
    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}

    def of(self, account_id: int) -> asyncio.Lock:
        return self._locks.setdefault(account_id, asyncio.Lock())
