"""Porta das opções do jogador (`account_options`). Message e Channel dependem disto."""

from typing import Protocol

from landmass_emu.protocol.message import LmRegisterInfo


class OptionsRepository(Protocol):
    async def get(self, account_id: int) -> LmRegisterInfo: ...

    async def save(self, account_id: int, options: LmRegisterInfo) -> None: ...
