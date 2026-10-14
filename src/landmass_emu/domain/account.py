"""Conta de jogo e token de login. Regras puras, sem IO."""

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import datetime

USERNAME_PATTERN = re.compile(r"[a-z0-9_]{1,12}")
NICKNAME_MAX_BYTES = 16
# Prefixo dos apelidos de bot (`domain/bots.BOT_PREFIX`, D231). Não importado: bots puxa o catálogo,
# que puxa este módulo.
NICKNAME_RESERVED_PREFIX = "[bot]"


@dataclass(frozen=True, slots=True)
class Account:
    id: int
    username: str
    nickname: str
    token_hash: str
    banned_until: datetime | None = None
    access_level: int = 0  # `ucAccess` do cliente; 9 ou mais tem comandos de GM (domain/access.py)
    password_hash: str | None = None  # scrypt (domain/passwords.py); nulo = sem login por senha


def is_banned(account: Account, now: datetime) -> bool:
    """Bloqueio temporário ainda vigente (D106). Expira sozinho: nada é apagado ao fim do prazo."""
    return account.banned_until is not None and now < account.banned_until


def new_token() -> str:
    """32 caracteres hexadecimais minúsculos: cabem em `login_num[33]` com NUL."""
    return secrets.token_hex(16)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.strip().lower().encode()).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), token_hash)


def check_username(username: str) -> None:
    if USERNAME_PATTERN.fullmatch(username) is None:
        raise ValueError("usuário: de 1 a 12 caracteres minúsculos, dígitos ou _")


def check_nickname(nickname: str) -> None:
    try:
        raw = nickname.encode("cp1252")
    except UnicodeEncodeError as e:
        raise ValueError("nickname: caractere fora do cp1252") from e
    if not 1 <= len(raw) <= NICKNAME_MAX_BYTES:
        raise ValueError("nickname: de 1 a 16 caracteres")
    # Prefixo reservado aos bots (D231): conta de jogador não pode começar com ele.
    if nickname.casefold().startswith(NICKNAME_RESERVED_PREFIX):
        raise ValueError("nickname: prefixo [BOT] é reservado aos bots")
