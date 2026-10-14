"""Operações da CLI sobre clãs: criar, entrar, sair, renomear, marcar e listar (F13, D55).

O cliente não tem pedido para estas ações. A CLI grava no banco e não avisa o servidor em
execução (D27): a mudança aparece quando a conta relogar.
"""

from landmass_emu.domain.account import Account
from landmass_emu.domain.clan import ClanError, ClanRules
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.clans import Clan, ClanRepository


class ClanAdmin:
    def __init__(
        self,
        accounts: AccountRepository,
        clans: ClanRepository,
        rules: ClanRules,
    ) -> None:
        self._accounts = accounts
        self._clans = clans
        self._rules = rules

    async def create(self, name: str, master_username: str, mark: int) -> str:
        name = self._rules.check_name(name)
        mark = self._rules.check_mark(mark)
        master = await self._account(master_username)
        clan = await self._clans.create(name, master.id, mark)
        return f"clã {clan.name} criado (id {clan.id}); mestre {master.nickname}"

    async def join(self, username: str, clan_name: str, grade: int) -> str:
        account = await self._account(username)
        clan = await self._clan(clan_name)
        await self._clans.add_member(clan.id, account.id, grade)
        return f"{account.nickname} entrou em {clan.name} (grau {grade})"

    async def leave(self, username: str) -> str:
        account = await self._account(username)
        clan = await self._clans.by_account(account.id)
        if clan is None:
            raise ClanError(f"{username} não tem clã")
        members = await self._clans.members(clan.id)
        self._rules.check_leave(
            is_master=clan.master_account_id == account.id,
            member_count=len(members),
        )
        await self._clans.remove_member(account.id)
        if len(members) == 1:
            await self._clans.delete(clan.id)  # clã sem membros não fica no banco
            return f"{account.nickname} saiu de {clan.name}; clã apagado (sem membros)"
        return f"{account.nickname} saiu de {clan.name}"

    async def rename(self, clan_name: str, new_name: str) -> str:
        clan = await self._clan(clan_name)
        new_name = self._rules.check_name(new_name)
        await self._clans.rename(clan.id, new_name)
        return f"clã {clan.name} renomeado para {new_name}"

    async def mark(self, clan_name: str, mark: int) -> str:
        clan = await self._clan(clan_name)
        mark = self._rules.check_mark(mark)
        await self._clans.set_mark(clan.id, mark)
        return f"marca de {clan.name} definida como {mark}"

    async def show(self, clan_name: str) -> str:
        clan = await self._clan(clan_name)
        head = f"clã {clan.name} (id {clan.id}, marca {clan.mark}, mestre {clan.master_nickname})"
        lines = [head]
        for member in await self._clans.members(clan.id):
            lines.append(f"  {member.nickname} grau {member.grade} exp {member.total_exp}")
        return "\n".join(lines)

    async def _account(self, username: str) -> Account:
        account = await self._accounts.find_by_username(username)
        if account is None:
            raise ClanError(f"conta {username!r} não existe")
        return account

    async def _clan(self, name: str) -> Clan:
        clan = await self._clans.by_name(name)
        if clan is None:
            raise ClanError(f"clã {name!r} não existe")
        return clan
