"""Consumo de item de sistema no SQLAlchemy: apaga a unidade e grava o efeito na conta, numa
transação (D72). Implementa `ports.consumables.ConsumableRepository`.

Apagar com `WHERE conta, índice e id` faz a corrida virar recusa: se a unidade já saiu, o rowcount é
0 e nada é gravado no saldo nem na conta.
"""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.models import AccountItemRow, AccountRow
from landmass_emu.domain.consumables import Effect


def _change(effect: int, value: int, at: datetime) -> dict[Any, Any]:
    """Campos da conta que cada efeito grava. Reset grava só o marco de zerado."""
    if effect == Effect.RESET_RECORD:
        return {AccountRow.record_reset_at: at, AccountRow.updated_at: at}
    if effect == Effect.RESET_COMBAT:
        return {AccountRow.combat_reset_at: at, AccountRow.updated_at: at}
    if effect == Effect.NEST:
        return {AccountRow.regular_nest_id: value, AccountRow.updated_at: at}
    return {AccountRow.regular_morat_class: value, AccountRow.updated_at: at}


class SqlConsumableRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def consume(
        self,
        account_id: int,
        inventory_index: int,
        catalog_id: int,
        effect: int,
        value: int,
        at: datetime,
    ) -> bool:
        async with self._sessions.begin() as session:
            removed = cast(
                "CursorResult[Any]",
                await session.execute(
                    delete(AccountItemRow).where(
                        AccountItemRow.account_id == account_id,
                        AccountItemRow.inventory_index == inventory_index,
                        AccountItemRow.catalog_id == catalog_id,
                    )
                ),
            )
            if removed.rowcount != 1:
                return False
            await _update_account(session, account_id, _change(effect, value, at))
        return True


async def _update_account(session: AsyncSession, account_id: int, values: dict[Any, Any]) -> None:
    await session.execute(update(AccountRow).where(AccountRow.id == account_id).values(values))
