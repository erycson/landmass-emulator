"""Conta de jogo e token de login. Regras puras, sem IO."""

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass

USER_ID_PATTERN = re.compile(r"[a-z0-9_]{1,12}")
NICKNAME_MAX_BYTES = 16


@dataclass(frozen=True, slots=True)
class Account:
    id: int
    user_id: str
    nickname: str
    token_hash: str


def new_token() -> str:
    """32 caracteres hexadecimais minúsculos: cabem em `login_num[33]` com NUL."""
    return secrets.token_hex(16)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.strip().lower().encode()).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), token_hash)


def check_user_id(user_id: str) -> None:
    if USER_ID_PATTERN.fullmatch(user_id) is None:
        raise ValueError("usuário: de 1 a 12 caracteres minúsculos, dígitos ou _")


def check_nickname(nickname: str) -> None:
    try:
        raw = nickname.encode("cp1252")
    except UnicodeEncodeError as e:
        raise ValueError("nickname: caractere fora do cp1252") from e
    if not 1 <= len(raw) <= NICKNAME_MAX_BYTES:
        raise ValueError("nickname: de 1 a 16 caracteres")
