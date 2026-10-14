"""Repositórios de clã e ranking sobre SQLite real: a migração `3f8a1c0d9e27` cria as tabelas."""

from pathlib import Path

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.app import open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.clans import SqlClanRepository
from landmass_emu.db.models import AccountRow
from landmass_emu.db.ranking import SqlRankingRepository
from landmass_emu.domain.account import hash_token
from landmass_emu.domain.ranking import RankedAccount, RankingRules
from landmass_emu.ports.clans import Clan, ClanConflict, ClanMember
from landmass_emu.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
    )


async def _set_exp(db: async_sessionmaker[AsyncSession], account_id: int, exp: int) -> None:
    async with db() as session:
        await session.execute(
            update(AccountRow).where(AccountRow.id == account_id).values(total_exp=exp)
        )
        await session.commit()


async def test_clan_guarda_mestre_como_membro_e_lista_na_ordem_de_entrada(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts = SqlAccountRepository(db)
        clans = SqlClanRepository(db)
        ana = await accounts.create("ana", "Ana", hash_token("a" * 32))
        bia = await accounts.create("bia", "Bia", hash_token("b" * 32))
        cai = await accounts.create("cai", "Cai", hash_token("c" * 32))

        clan = await clans.create("Nova", ana.id, 3)
        await clans.add_member(clan.id, bia.id, 1)

        assert clan == Clan(clan.id, "Nova", 3, ana.id, "Ana")
        assert await clans.members(clan.id) == (
            ClanMember(ana.id, "Ana", 0, 0),
            ClanMember(bia.id, "Bia", 0, 1),
        )
        assert await clans.by_account(bia.id) == clan
        assert await clans.by_account(cai.id) is None


async def test_conta_so_tem_um_clan_e_o_nome_e_unico(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts = SqlAccountRepository(db)
        clans = SqlClanRepository(db)
        ana = await accounts.create("ana", "Ana", hash_token("a" * 32))
        bia = await accounts.create("bia", "Bia", hash_token("b" * 32))
        clan = await clans.create("Nova", ana.id, 0)

        with pytest.raises(ClanConflict):
            await clans.create("Outro", ana.id, 0)  # a conta do mestre já tem clã
        assert await clans.by_name("Outro") is None  # a linha do clã não sobra

        with pytest.raises(ClanConflict):
            await clans.create("Nova", bia.id, 0)  # nome repetido
        await clans.add_member(clan.id, bia.id, 0)
        with pytest.raises(ClanConflict):
            await clans.add_member(clan.id, bia.id, 0)  # já é membro


async def test_rename_mark_remocao_e_delete(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts = SqlAccountRepository(db)
        clans = SqlClanRepository(db)
        ana = await accounts.create("ana", "Ana", hash_token("a" * 32))
        bia = await accounts.create("bia", "Bia", hash_token("b" * 32))
        other = await clans.create("Outra", bia.id, 0)
        clan = await clans.create("Nova", ana.id, 0)

        await clans.rename(clan.id, "Velha")
        await clans.set_mark(clan.id, 9)
        assert await clans.by_name("Velha") == Clan(clan.id, "Velha", 9, ana.id, "Ana")
        with pytest.raises(ClanConflict):
            await clans.rename(clan.id, "Outra")

        await clans.remove_member(ana.id)
        assert await clans.by_account(ana.id) is None
        await clans.delete(clan.id)
        assert await clans.by_name("Velha") is None
        assert await clans.by_name("Outra") == other


async def test_ranking_ordena_por_exp_e_id_e_traz_o_clan(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts = SqlAccountRepository(db)
        clans = SqlClanRepository(db)
        ana = await accounts.create("ana", "Ana", hash_token("a" * 32))
        bia = await accounts.create("bia", "Bia", hash_token("b" * 32))
        cai = await accounts.create("cai", "Cai", hash_token("c" * 32))
        dan = await accounts.create("dan", "Dan", hash_token("d" * 32))
        await _set_exp(db, ana.id, 500)
        await _set_exp(db, bia.id, 500)
        await _set_exp(db, cai.id, 300)
        clan = await clans.create("Nova", ana.id, 0)

        rows = await SqlRankingRepository(db).top(100)

        assert rows == (
            RankedAccount(ana.id, "Ana", 500, clan.id),
            RankedAccount(bia.id, "Bia", 500, 0),
            RankedAccount(cai.id, "Cai", 300, 0),
            RankedAccount(dan.id, "Dan", 0, 0),
        )
        assert [p.rank for p in RankingRules().positions(rows)] == [1, 1, 3, 4]


async def test_ranking_respeita_o_limite(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts = SqlAccountRepository(db)
        for i in range(5):
            await accounts.create(f"u{i}", f"N{i}", hash_token(f"{i}" * 32))

        assert len(await SqlRankingRepository(db).top(3)) == 3
