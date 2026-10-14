"""Compra no SQLAlchemy: débito condicional e criação da unidade na mesma transação (R-DEB-01).
Implementa `ports.shop.ShopRepository`. `debit` é reusado pela extensão de prazo (F7)."""

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.inventory import item_row, morat_row
from landmass_emu.db.models import AccountRow
from landmass_emu.domain.currency import Currency
from landmass_emu.domain.inventory import ItemUnit, MoratUnit
from landmass_emu.ports.inventory import InventoryConflict


async def debit(
    session: AsyncSession, account_id: int, currency: Currency, price: int, now: datetime
) -> bool:
    """Débito condicional (`WHERE saldo >= preço`, sem leitura antes). Rowcount 0: sem saldo."""
    saldo = AccountRow.ld if currency is Currency.LD else AccountRow.cash
    result = cast(
        "CursorResult[Any]",
        await session.execute(
            update(AccountRow)
            .where(AccountRow.id == account_id, saldo >= price)
            .values({saldo: saldo - price, AccountRow.updated_at: now})
        ),
    )
    return result.rowcount == 1


class SqlShopRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def purchase(
        self, account_id: int, currency: Currency, price: int, unit: ItemUnit | MoratUnit
    ) -> bool:
        now = datetime.now(UTC)
        row = item_row(unit, now) if isinstance(unit, ItemUnit) else morat_row(unit, now)
        try:
            async with self._sessions.begin() as session:
                if not await debit(session, account_id, currency, price, now):
                    return False
                session.add(row)
        except IntegrityError as e:
            # Commit recusado: a transação inteira volta, inclusive o débito.
            raise InventoryConflict("índice ou gate já ocupado na conta") from e
        return True
