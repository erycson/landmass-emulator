"""Repositório de amizades e bloqueios em SQLAlchemy async (`ports.social.SocialRepository`)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import InstrumentedAttribute

from landmass_emu.db.models import AccountRow, BlockRow, FriendRow
from landmass_emu.ports.social import Contact, Relation

# Tabela da relação e a coluna do alvo (nomes da convenção Laravel, D11).
_EDGES: dict[
    Relation,
    tuple[type[FriendRow] | type[BlockRow], InstrumentedAttribute[int]],
] = {
    Relation.FRIEND: (FriendRow, FriendRow.friend_account_id),
    Relation.BLOCK: (BlockRow, BlockRow.blocked_account_id),
}


class SqlSocialRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def contacts(self, relation: Relation, account_id: int) -> tuple[Contact, ...]:
        model, target = _EDGES[relation]
        stmt = (
            select(AccountRow.id, AccountRow.nickname, AccountRow.total_exp)
            .select_from(model)
            .join(AccountRow, target == AccountRow.id)
            .where(model.account_id == account_id)
            .order_by(model.id)
        )
        async with self._sessions() as session:
            rows = (await session.execute(stmt)).all()
        return tuple(Contact(r.id, r.nickname, r.total_exp) for r in rows)

    async def has(self, relation: Relation, account_id: int, target_id: int) -> bool:
        model, target = _EDGES[relation]
        async with self._sessions() as session:
            found = await session.scalar(
                select(model.id).where(model.account_id == account_id, target == target_id)
            )
        return found is not None

    async def add(self, relation: Relation, account_id: int, target_id: int) -> bool:
        model, target = _EDGES[relation]
        now = datetime.now(UTC)
        try:
            async with self._sessions.begin() as session:
                session.add(
                    model(
                        account_id=account_id,
                        created_at=now,
                        updated_at=now,
                        **{target.key: target_id},
                    )
                )
        except IntegrityError:
            # Par já existe (unique). Conta inexistente (FK) também cai aqui: o handler valida.
            return False
        return True

    async def remove(self, relation: Relation, account_id: int, target_id: int) -> bool:
        model, target = _EDGES[relation]
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(model).where(model.account_id == account_id, target == target_id)
            )
            if row is None:
                return False
            await session.delete(row)
        return True
