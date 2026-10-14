"""Compra no SQLAlchemy: débito condicional e criação da unidade na mesma transação (R-DEB-01).
Implementa `ports.shop.ShopRepository`."""

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


class SqlShopRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def purchase(
        self, account_id: int, currency: Currency, price: int, unit: ItemUnit | MoratUnit
    ) -> bool:
        saldo = AccountRow.ld if currency is Currency.LD else AccountRow.cash
        now = datetime.now(UTC)
        row = item_row(unit, now) if isinstance(unit, ItemUnit) else morat_row(unit, now)
        try:
            async with self._sessions.begin() as session:
                # WHERE garante saldo ≥ preço: rowcount 0 é saldo insuficiente (sem leitura antes).
                debit = cast(
                    "CursorResult[Any]",
                    await session.execute(
                        update(AccountRow)
                        .where(AccountRow.id == account_id, saldo >= price)
                        .values({saldo: saldo - price, AccountRow.updated_at: now})
                    ),
                )
                if debit.rowcount != 1:
                    return False
                session.add(row)
        except IntegrityError as e:
            # Commit recusado: a transação inteira volta, inclusive o débito.
            raise InventoryConflict("índice ou gate já ocupado na conta") from e
        return True
