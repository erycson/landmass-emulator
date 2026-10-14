"""Depósito no SQLAlchemy: envio com débito do remetente na mesma transação, página de pendentes e
resgate com a unidade gravada no inventário (F10). Implementa `ports.gifts.GiftRepository`."""

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.inventory import item_row
from landmass_emu.db.models import GiftRow
from landmass_emu.db.shop import debit
from landmass_emu.domain.currency import Currency
from landmass_emu.domain.gift import Gift
from landmass_emu.domain.inventory import ItemUnit
from landmass_emu.ports.inventory import InventoryConflict

# Chave u16 do cliente: `*(short*)param_2` no dispatcher de 611 e no 612.
MAX_SLOT = 0xFFFF


def _gift(row: GiftRow) -> Gift:
    return Gift(
        id=row.id,
        sender_account_id=row.sender_account_id,
        receiver_account_id=row.receiver_account_id,
        slot=row.slot,
        catalog_id=row.catalog_id,
        duration_days=row.duration_days,
    )


async def _next_slot(session: AsyncSession, receiver_id: int) -> int:
    """Menor chave livre entre os pendentes do destinatário. Na mesma transação do envio."""
    taken = set(
        await session.scalars(
            select(GiftRow.slot).where(
                GiftRow.receiver_account_id == receiver_id, GiftRow.claimed_at.is_(None)
            )
        )
    )
    for slot in range(1, MAX_SLOT + 1):
        if slot not in taken:
            return slot
    raise InventoryConflict("Depósito cheio: 65535 presentes pendentes")


class SqlGiftRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def page(self, account_id: int, page: int, size: int) -> list[Gift]:
        stmt = (
            select(GiftRow)
            .where(GiftRow.receiver_account_id == account_id, GiftRow.claimed_at.is_(None))
            .order_by(GiftRow.slot)
            .offset(page * size)
            .limit(size)
        )
        async with self._sessions() as session:
            rows = await session.scalars(stmt)
            return [_gift(row) for row in rows.all()]

    async def pending(self, account_id: int, slot: int) -> Gift | None:
        stmt = select(GiftRow).where(
            GiftRow.receiver_account_id == account_id,
            GiftRow.slot == slot,
            GiftRow.claimed_at.is_(None),
        )
        async with self._sessions() as session:
            row = await session.scalar(stmt)
            return None if row is None else _gift(row)

    async def send(
        self,
        sender_id: int,
        receiver_id: int,
        currency: Currency,
        price: int,
        catalog_id: int,
        days: int,
    ) -> bool:
        now = datetime.now(UTC)
        try:
            async with self._sessions.begin() as session:
                if not await debit(session, sender_id, currency, price, now):
                    return False
                session.add(
                    GiftRow(
                        sender_account_id=sender_id,
                        receiver_account_id=receiver_id,
                        slot=await _next_slot(session, receiver_id),
                        catalog_id=catalog_id,
                        duration_days=days,
                        claimed_at=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
        except IntegrityError as e:
            raise InventoryConflict("presente não gravado: conflito de chave") from e
        return True

    async def claim(self, gift: Gift, unit: ItemUnit) -> bool:
        now = datetime.now(UTC)
        try:
            async with self._sessions.begin() as session:
                result = cast(
                    "CursorResult[Any]",
                    await session.execute(
                        update(GiftRow)
                        .where(GiftRow.id == gift.id, GiftRow.claimed_at.is_(None))
                        .values(claimed_at=now, updated_at=now)
                    ),
                )
                if result.rowcount != 1:
                    return False
                session.add(item_row(unit, now))
        except IntegrityError as e:
            raise InventoryConflict("índice ou guid já ocupado na conta") from e
        return True
