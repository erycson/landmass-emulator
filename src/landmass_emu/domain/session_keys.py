"""Chaves de sessão do Message para o Channel. Regras puras em memória, sem IO.

Uma chave por conta: emitir outra invalida a anterior. Chave que nunca foi usada no Channel
expira `SESSION_KEY_TTL` segundos após a emissão. Depois do primeiro uso ela vale até ser
reemitida. A expiração é checada no `resolve`; não há tarefa de fundo.
"""

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

from landmass_emu.domain.account import Account

SESSION_KEY_TTL = 300.0


@dataclass(slots=True)
class _Entry:
    account: Account
    issued_at: float
    used: bool = False


class MemorySessionKeyRegistry:
    """Implementa `ports.session_keys.SessionKeyRegistry`. Acessado só pelo loop de eventos."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._entries: dict[str, _Entry] = {}

    def issue(self, account: Account) -> str:
        now = self._clock()
        # Poda chaves desta conta (a anterior morre aqui) e chaves não usadas já expiradas.
        # Indexa por `id`: a igualdade de `Account` compara também hash e nickname.
        self._entries = {
            k: e
            for k, e in self._entries.items()
            if e.account.id != account.id and (e.used or now - e.issued_at < SESSION_KEY_TTL)
        }
        key = secrets.token_hex(16)  # 32 hex minúsculos: cabem em char[33] com NUL
        self._entries[key] = _Entry(account, now)
        return key

    def resolve(self, key: str) -> Account | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if not entry.used:
            if self._clock() - entry.issued_at >= SESSION_KEY_TTL:
                del self._entries[key]
                return None
            entry.used = True
        return entry.account
