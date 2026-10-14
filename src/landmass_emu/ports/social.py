"""Porta de amizades e bloqueios. Handlers do Message dependem disto, nunca do SQLAlchemy."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class Relation(StrEnum):
    FRIEND = "friend"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class Contact:
    """Conta da relação, com os campos que o registro 183 e 188 leva."""

    account_id: int
    nickname: str
    total_exp: int


class SocialRepository(Protocol):
    async def contacts(self, relation: Relation, account_id: int) -> tuple[Contact, ...]: ...

    async def has(self, relation: Relation, account_id: int, target_id: int) -> bool: ...

    async def add(self, relation: Relation, account_id: int, target_id: int) -> bool:
        """Cria a relação. Devolve False se ela já existia."""
        ...

    async def remove(self, relation: Relation, account_id: int, target_id: int) -> bool:
        """Desfaz a relação. Devolve False se ela não existia."""
        ...
