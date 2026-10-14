"""Montagem, destruição e prazo no SQLAlchemy. Implementa `ports.equipment.EquipmentRepository`.

Cada método é uma transação. O SQLite deste projeto não liga `PRAGMA foreign_keys`, então o
`ON DELETE SET NULL` de `account_items.account_morat_id` não é confiável: zeramos a montagem na mão.
"""

from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.models import AccountItemRow, AccountMoratRow
from landmass_emu.db.shop import debit
from landmass_emu.domain.currency import Currency
from landmass_emu.ports.inventory import InventoryConflict


async def _item(session: AsyncSession, account_id: int, inventory_index: int) -> AccountItemRow:
    row = await session.scalar(
        select(AccountItemRow).where(
            AccountItemRow.account_id == account_id,
            AccountItemRow.inventory_index == inventory_index,
        )
    )
    if row is None:
        raise InventoryConflict(f"índice {inventory_index} não existe na conta")
    return row


class SqlEquipmentRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def mount(
        self, account_id: int, inventory_index: int, morat_id: int, slot_name: str
    ) -> None:
        try:
            async with self._sessions.begin() as session:
                row = await _item(session, account_id, inventory_index)
                previous = await session.scalar(
                    select(AccountItemRow).where(
                        AccountItemRow.account_morat_id == morat_id,
                        AccountItemRow.slot_name == slot_name,
                    )
                )
                if previous is not None:
                    # Solta a peça antiga antes de ocupar o slot: o UNIQUE não aceita as duas.
                    previous.account_morat_id = None
                    previous.slot_name = None
                    await session.flush()
                row.account_morat_id = morat_id
                row.slot_name = slot_name
        except IntegrityError as e:
            raise InventoryConflict(f"slot {slot_name} ocupado no morat") from e

    async def unmount(self, account_id: int, inventory_index: int) -> None:
        async with self._sessions.begin() as session:
            row = await _item(session, account_id, inventory_index)
            row.account_morat_id = None
            row.slot_name = None

    async def set_system_slot(self, account_id: int, inventory_index: int, slot: int) -> None:
        try:
            async with self._sessions.begin() as session:
                row = await _item(session, account_id, inventory_index)
                row.system_slot = slot
        except IntegrityError as e:
            raise InventoryConflict(f"slot de sistema {slot} já ocupado") from e

    async def destroy_item(self, account_id: int, inventory_index: int) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                delete(AccountItemRow).where(
                    AccountItemRow.account_id == account_id,
                    AccountItemRow.inventory_index == inventory_index,
                )
            )

    async def destroy_morat(self, account_id: int, morat_id: int) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                update(AccountItemRow)
                .where(
                    AccountItemRow.account_id == account_id,
                    AccountItemRow.account_morat_id == morat_id,
                )
                .values(account_morat_id=None, slot_name=None)
            )
            await session.execute(
                delete(AccountMoratRow).where(
                    AccountMoratRow.account_id == account_id, AccountMoratRow.id == morat_id
                )
            )

    async def extend(
        self,
        account_id: int,
        currency: Currency,
        price: int,
        inventory_index: int,
        expires_at: datetime,
    ) -> bool:
        now = datetime.now(UTC)
        async with self._sessions.begin() as session:
            if not await debit(session, account_id, currency, price, now):
                return False
            await session.execute(
                update(AccountItemRow)
                .where(
                    AccountItemRow.account_id == account_id,
                    AccountItemRow.inventory_index == inventory_index,
                )
                .values(expires_at=expires_at.astimezone(UTC), updated_at=now)
            )
        return True
