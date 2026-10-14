"""Atalhos da conta no SQLAlchemy. Implementa `ports.quick_slots.QuickSlotRepository`."""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.models import AccountQuickSlotRow
from landmass_emu.domain.quick_slots import QuickSlot


class SqlQuickSlotRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def seed(self, account_id: int, slots: Sequence[QuickSlot]) -> int:
        now = datetime.now(UTC)
        async with self._sessions.begin() as session:
            have = await session.scalars(
                select(AccountQuickSlotRow.slot_index).where(
                    AccountQuickSlotRow.account_id == account_id
                )
            )
            taken = set(have)
            missing = [slot for slot in slots if slot.slot_index not in taken]
            session.add_all(
                AccountQuickSlotRow(
                    account_id=account_id,
                    slot_index=slot.slot_index,
                    enabled=int(slot.enabled),
                    memo=slot.memo,
                    gate_index=slot.gate_index,
                    created_at=now,
                    updated_at=now,
                )
                for slot in missing
            )
        return len(missing)

    async def slots(self, account_id: int) -> list[QuickSlot]:
        stmt = (
            select(AccountQuickSlotRow)
            .where(AccountQuickSlotRow.account_id == account_id)
            .order_by(AccountQuickSlotRow.slot_index)
        )
        async with self._sessions() as session:
            rows = await session.scalars(stmt)
            return [
                QuickSlot(
                    slot_index=row.slot_index,
                    enabled=bool(row.enabled),
                    memo=row.memo,
                    gate_index=row.gate_index,
                )
                for row in rows.all()
            ]
