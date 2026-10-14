"""Repositório de inventário em SQLAlchemy. Implementa `ports.inventory.InventoryRepository`."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.models import AccountItemRow, AccountMoratRow
from landmass_emu.domain.inventory import ApplyFlag, ItemUnit, MoratUnit
from landmass_emu.ports.inventory import InventoryConflict


def _aware(value: datetime | None) -> datetime | None:
    # SQLite devolve datetime sem fuso. Tudo é gravado em UTC, então o fuso volta a ser UTC.
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _item(row: AccountItemRow) -> ItemUnit:
    return ItemUnit(
        account_id=row.account_id,
        inventory_index=row.inventory_index,
        catalog_id=row.catalog_id,
        item_guid=row.item_guid,
        apply_flag=ApplyFlag(row.apply_flag),
        apply_value=row.apply_value,
        expires_at=_aware(row.expires_at),
        account_morat_id=row.account_morat_id,
        slot_name=row.slot_name,
        system_slot=row.system_slot,
    )


def _morat(row: AccountMoratRow) -> MoratUnit:
    return MoratUnit(
        account_id=row.account_id,
        inventory_index=row.inventory_index,
        catalog_id=row.catalog_id,
        item_guid=row.item_guid,
        gate_index=row.gate_index,
        apply_flag=ApplyFlag(row.apply_flag),
        apply_value=row.apply_value,
        expires_at=_aware(row.expires_at),
        id=row.id,
    )


def item_row(item: ItemUnit, now: datetime) -> AccountItemRow:
    return AccountItemRow(
        account_id=item.account_id,
        inventory_index=item.inventory_index,
        catalog_id=item.catalog_id,
        item_guid=item.item_guid,
        apply_flag=int(item.apply_flag),
        apply_value=item.apply_value,
        expires_at=item.expires_at and item.expires_at.astimezone(UTC),
        created_at=now,
        updated_at=now,
    )


def morat_row(morat: MoratUnit, now: datetime) -> AccountMoratRow:
    return AccountMoratRow(
        account_id=morat.account_id,
        inventory_index=morat.inventory_index,
        catalog_id=morat.catalog_id,
        item_guid=morat.item_guid,
        gate_index=morat.gate_index,
        apply_flag=int(morat.apply_flag),
        apply_value=morat.apply_value,
        expires_at=morat.expires_at and morat.expires_at.astimezone(UTC),
        created_at=now,
        updated_at=now,
    )


class SqlInventoryRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def items(self, account_id: int) -> list[ItemUnit]:
        stmt = (
            select(AccountItemRow)
            .where(AccountItemRow.account_id == account_id)
            .order_by(AccountItemRow.inventory_index)
        )
        async with self._sessions() as session:
            rows = await session.scalars(stmt)
            return [_item(row) for row in rows.all()]

    async def morats(self, account_id: int) -> list[MoratUnit]:
        stmt = (
            select(AccountMoratRow)
            .where(AccountMoratRow.account_id == account_id)
            .order_by(AccountMoratRow.inventory_index)
        )
        async with self._sessions() as session:
            rows = await session.scalars(stmt)
            return [_morat(row) for row in rows.all()]

    async def add_item(self, item: ItemUnit) -> None:
        row = item_row(item, datetime.now(UTC))
        await self._insert(row, f"índice {item.inventory_index} já existe na conta")

    async def add_morat(self, morat: MoratUnit) -> None:
        row = morat_row(morat, datetime.now(UTC))
        await self._insert(row, f"gate {morat.gate_index} já tem um morat na conta")

    async def _insert(self, row: AccountItemRow | AccountMoratRow, conflict: str) -> None:
        try:
            async with self._sessions.begin() as session:
                session.add(row)
        except IntegrityError as e:
            raise InventoryConflict(conflict) from e
