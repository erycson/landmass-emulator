"""Compra no SQLAlchemy: débito condicional e criação da unidade na mesma transação (R-DEB-01).
Implementa `ports.shop.ShopRepository`. `debit` é reusado pela extensão de prazo (F7).
`SqlShopItemRepository` guarda a venda por id do catálogo (`shop_items`, D191)."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.inventory import item_row, morat_row
from landmass_emu.db.models import AccountRow, ShopItemRow
from landmass_emu.domain.currency import Currency
from landmass_emu.domain.inventory import ItemUnit, MoratUnit
from landmass_emu.ports.inventory import InventoryConflict
from landmass_emu.ports.shop import ShopItem


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


class SqlShopItemRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get(self, catalog_id: int) -> ShopItem | None:
        async with self._sessions() as session:
            row = await session.get(ShopItemRow, catalog_id)
        return None if row is None else _item(row)

    async def all_items(self) -> tuple[ShopItem, ...]:
        stmt = select(ShopItemRow).order_by(ShopItemRow.catalog_id)
        async with self._sessions() as session:
            rows = (await session.scalars(stmt)).all()
        return tuple(_item(row) for row in rows)

    async def count(self) -> int:
        async with self._sessions() as session:
            total = await session.scalar(select(func.count()).select_from(ShopItemRow))
        return int(total or 0)

    async def sync(self, items: Sequence[ShopItem]) -> tuple[int, int]:
        now = datetime.now(UTC)
        novas = atualizadas = 0
        async with self._sessions.begin() as session:
            existentes = {
                row.catalog_id: row for row in (await session.scalars(select(ShopItemRow))).all()
            }
            for item in items:
                row = existentes.get(item.catalog_id)
                if row is None:
                    session.add(_new_row(item, now))
                    novas += 1
                    continue
                # `enabled` não entra: a escolha de habilitar ou desativar é da CLI, não do wdb.
                row.name = item.name
                _write_prices(row, item.ld, item.cash)
                row.updated_at = now
                atualizadas += 1
        return novas, atualizadas

    async def set_enabled(self, catalog_id: int, enabled: bool) -> bool:
        async with self._sessions.begin() as session:
            row = await session.get(ShopItemRow, catalog_id)
            if row is None:
                return False
            row.enabled = enabled
            row.updated_at = datetime.now(UTC)
        return True

    async def set_prices(
        self, catalog_id: int, ld: tuple[int, int, int, int], cash: tuple[int, int, int, int]
    ) -> bool:
        async with self._sessions.begin() as session:
            row = await session.get(ShopItemRow, catalog_id)
            if row is None:
                return False
            _write_prices(row, ld, cash)
            row.updated_at = datetime.now(UTC)
        return True


def _item(row: ShopItemRow) -> ShopItem:
    return ShopItem(
        row.catalog_id,
        row.name,
        row.enabled,
        (row.point_0, row.point_1, row.point_2, row.point_3),
        (row.cash_0, row.cash_1, row.cash_2, row.cash_3),
    )


def _new_row(item: ShopItem, now: datetime) -> ShopItemRow:
    row = ShopItemRow(
        catalog_id=item.catalog_id,
        name=item.name,
        enabled=item.enabled,
        created_at=now,
        updated_at=now,
    )
    _write_prices(row, item.ld, item.cash)
    return row


def _write_prices(
    row: ShopItemRow, ld: tuple[int, int, int, int], cash: tuple[int, int, int, int]
) -> None:
    row.point_0, row.point_1, row.point_2, row.point_3 = ld
    row.cash_0, row.cash_1, row.cash_2, row.cash_3 = cash
