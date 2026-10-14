"""Porta de clãs. Handlers do Message e a CLI dependem disto, nunca do SQLAlchemy."""

from dataclasses import dataclass
from typing import Protocol


class ClanConflict(Exception):
    """Nome de clã já existe, ou a conta já tem clã."""


@dataclass(frozen=True, slots=True)
class Clan:
    id: int
    name: str
    mark: int
    master_account_id: int
    master_nickname: str


@dataclass(frozen=True, slots=True)
class ClanMember:
    account_id: int
    nickname: str
    total_exp: int
    grade: int


class ClanRepository(Protocol):
    async def by_account(self, account_id: int) -> Clan | None:
        """Clã da conta, ou None se ela não tem clã."""
        ...

    async def by_name(self, name: str) -> Clan | None: ...

    async def members(self, clan_id: int) -> tuple[ClanMember, ...]:
        """Membros na ordem de entrada (id da linha de membro)."""
        ...

    async def create(self, name: str, master_account_id: int, mark: int) -> Clan:
        """Cria o clã e põe o mestre como membro de grau 0. Levanta `ClanConflict`."""
        ...

    async def add_member(self, clan_id: int, account_id: int, grade: int) -> None:
        """Levanta `ClanConflict` se a conta já tem clã."""
        ...

    async def remove_member(self, account_id: int) -> None: ...

    async def delete(self, clan_id: int) -> None:
        """Apaga o clã e os membros que restarem. Chamado só com o clã vazio."""
        ...

    async def rename(self, clan_id: int, name: str) -> None:
        """Levanta `ClanConflict` se o nome já existe."""
        ...

    async def set_mark(self, clan_id: int, mark: int) -> None: ...
