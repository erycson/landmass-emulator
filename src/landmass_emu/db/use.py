"""Uso de item especial no SQLAlchemy: apaga a unidade, credita LD, grava prêmios e troca a contagem
de gates na mesma transação (D20). Implementa `ports.use.UseRepository`."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.inventory import item_row
from landmass_emu.db.models import AccountItemRow, AccountRow
from landmass_emu.domain.inventory import ItemUnit
from landmass_emu.ports.inventory import InventoryConflict


class SqlUseRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def consume(
        self,
        account_id: int,
        index: int,
        catalog_id: int,
        *,
        ld: int,
        grants: Sequence[ItemUnit],
        gate_count: int | None,
    ) -> bool:
        now = datetime.now(UTC)
        try:
            async with self._sessions.begin() as session:
                gone = cast(
                    "CursorResult[Any]",
                    await session.execute(
                        delete(AccountItemRow).where(
                            AccountItemRow.account_id == account_id,
                            AccountItemRow.inventory_index == index,
                            AccountItemRow.catalog_id == catalog_id,
                        )
                    ),
                )
                if gone.rowcount != 1:
                    return False
                values: dict[Any, Any] = {}
                if ld:
                    values[AccountRow.ld] = AccountRow.ld + ld
                if gate_count is not None:
                    values[AccountRow.gate_count] = gate_count
                if values:
                    values[AccountRow.updated_at] = now
                    await session.execute(
                        update(AccountRow).where(AccountRow.id == account_id).values(values)
                    )
                for unit in grants:
                    session.add(item_row(unit, now))
        except IntegrityError as e:
            raise InventoryConflict("índice já ocupado na conta") from e
        return True
