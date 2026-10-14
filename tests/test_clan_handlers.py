"""Handlers de clã (F13) e ranking (F14) com SQLite real e presença em memória."""

import struct
from pathlib import Path

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.app import open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.clans import SqlClanRepository
from landmass_emu.db.models import AccountRow
from landmass_emu.db.options import SqlOptionsRepository
from landmass_emu.db.ranking import SqlRankingRepository
from landmass_emu.domain.account import Account, hash_token
from landmass_emu.domain.presence import MessagePresence
from landmass_emu.domain.session_keys import MemorySessionKeyRegistry
from landmass_emu.handlers.message.account import AccountHandlers
from landmass_emu.handlers.message.clan import ClanHandlers
from landmass_emu.handlers.message.ranking import RankingHandlers
from landmass_emu.net.server import reply_body
from landmass_emu.net.session import Session
from landmass_emu.ports.clans import ClanRepository
from landmass_emu.protocol.header import MESSAGE_NET_CODE
from landmass_emu.protocol.message import (
    MsClanChatOut,
    MsClanInfoOut,
    MsClanMemberOut,
    MsClanRecord,
    MsInMessageServerOut,
    MsRankingInfoOut,
    MsRefreshClanOut,
    MsRelationIdsIn,
    RankingEntry,
)
from landmass_emu.settings import Settings


class FakeRecipient:
    """Destino de corpos: guarda o que foi enviado, na ordem."""

    def __init__(self) -> None:
        self.bodies: list[bytes] = []

    def send(self, body: bytes) -> None:
        self.bodies.append(body)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
    )


def _session(account: Account | None) -> Session:
    return Session(peer="teste", account=account)


async def _set_exp(db: async_sessionmaker[AsyncSession], account_id: int, exp: int) -> None:
    async with db() as session:
        await session.execute(
            update(AccountRow).where(AccountRow.id == account_id).values(total_exp=exp)
        )
        await session.commit()


async def _elenco(
    db: async_sessionmaker[AsyncSession],
) -> tuple[SqlAccountRepository, ClanRepository]:
    return SqlAccountRepository(db), SqlClanRepository(db)


async def test_171_e_174_so_mostram_o_proprio_clan(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts, clans = await _elenco(db)
        ana = await accounts.create("ana", "Ana", hash_token("a" * 32))
        bia = await accounts.create("bia", "Bia", hash_token("b" * 32))
        cai = await accounts.create("cai", "Cai", hash_token("c" * 32))
        clan = await clans.create("Nova", ana.id, 3)
        await clans.add_member(clan.id, bia.id, 0)
        presence = MessagePresence()
        presence.bind(bia.id, FakeRecipient())
        handlers = ClanHandlers(clans, presence)

        assert await handlers.get_clan_info(_session(bia), b"") == [
            MsClanInfoOut(clan.id, "Nova", "Ana", 3)
        ]
        assert await handlers.get_clan_member(_session(bia), b"") == [
            MsClanMemberOut(ana.id, "Ana", 0, online=False),
            MsClanMemberOut(bia.id, "Bia", 0, online=True),
        ]
        assert await handlers.get_clan_info(_session(cai), b"") == []
        assert await handlers.get_clan_member(_session(cai), b"") == []
        assert await handlers.get_clan_info(_session(None), b"") == []


async def test_177_entrega_so_a_membros_online_inclusive_quem_enviou(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts, clans = await _elenco(db)
        ana = await accounts.create("ana", "Ana", hash_token("a" * 32))
        bia = await accounts.create("bia", "Bia", hash_token("b" * 32))
        dan = await accounts.create("dan", "Dan", hash_token("d" * 32))  # membro offline
        cai = await accounts.create("cai", "Cai", hash_token("c" * 32))  # fora do clã, online
        clan = await clans.create("Nova", ana.id, 0)
        await clans.add_member(clan.id, bia.id, 0)
        await clans.add_member(clan.id, dan.id, 0)
        presence = MessagePresence()
        rec_ana, rec_bia, rec_cai = FakeRecipient(), FakeRecipient(), FakeRecipient()
        presence.bind(ana.id, rec_ana)
        presence.bind(bia.id, rec_bia)
        presence.bind(cai.id, rec_cai)
        handlers = ClanHandlers(clans, presence)

        replies = await handlers.send_clan_message(_session(ana), struct.pack("<H", 2) + b"oi")

        esperado = reply_body(MsClanChatOut("Ana", b"oi"), MESSAGE_NET_CODE)
        assert replies == []
        assert rec_ana.bodies == [esperado]
        assert rec_bia.bodies == [esperado]
        assert rec_cai.bodies == []


async def test_177_de_quem_nao_tem_clan_e_ignorado(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts, clans = await _elenco(db)
        cai = await accounts.create("cai", "Cai", hash_token("c" * 32))
        rec = FakeRecipient()
        presence = MessagePresence()
        presence.bind(cai.id, rec)

        replies = await ClanHandlers(clans, presence).send_clan_message(
            _session(cai), struct.pack("<H", 2) + b"oi"
        )

        assert replies == []
        assert rec.bodies == []


async def test_177_com_len_acima_de_0x78_nao_entrega(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts, clans = await _elenco(db)
        ana = await accounts.create("ana", "Ana", hash_token("a" * 32))
        await clans.create("Nova", ana.id, 0)
        rec = FakeRecipient()
        presence = MessagePresence()
        presence.bind(ana.id, rec)

        with pytest.raises(ValueError, match="inconsistente"):
            await ClanHandlers(clans, presence).send_clan_message(
                _session(ana), struct.pack("<H", 0x79) + b"x" * 0x79
            )
        assert rec.bodies == []


async def test_194_responde_so_com_membros_do_proprio_clan(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts, clans = await _elenco(db)
        ana = await accounts.create("ana", "Ana", hash_token("a" * 32))
        cai = await accounts.create("cai", "Cai", hash_token("c" * 32))
        clan = await clans.create("Nova", ana.id, 4)
        presence = MessagePresence()
        presence.bind(ana.id, FakeRecipient())

        replies = await ClanHandlers(clans, presence).refresh_clan(
            _session(ana), MsRelationIdsIn((ana.id, cai.id)).pack()
        )

        assert replies == [
            MsRefreshClanOut(clan.id, 4, (MsClanRecord(ana.id, 0, online=True),)),
        ]


async def test_121_leva_o_clan_code_do_proprio_clan(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts, clans = await _elenco(db)
        ana = await accounts.create("ana", "Ana", hash_token("a" * 32))
        bia = await accounts.create("bia", "Bia", hash_token("b" * 32))
        clan = await clans.create("Nova", ana.id, 0)
        handlers = AccountHandlers(
            accounts,
            MemorySessionKeyRegistry(),
            SqlOptionsRepository(db),
            MessagePresence(),
            clans,
        )

        assert await handlers.in_message_server(_session(ana), b"") == [
            MsInMessageServerOut(0, "Ana", clan.id)
        ]
        assert await handlers.in_message_server(_session(bia), b"") == [
            MsInMessageServerOut(0, "Bia", 0)
        ]


async def test_170_responde_171_com_posicoes_e_clan(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts, clans = await _elenco(db)
        ana = await accounts.create("ana", "Ana", hash_token("a" * 32))
        bia = await accounts.create("bia", "Bia", hash_token("b" * 32))
        cai = await accounts.create("cai", "Cai", hash_token("c" * 32))
        await _set_exp(db, ana.id, 500)
        await _set_exp(db, bia.id, 500)
        await _set_exp(db, cai.id, 300)
        clan = await clans.create("Nova", ana.id, 0)

        replies = await RankingHandlers(SqlRankingRepository(db)).get_ranking(_session(ana), b"")

        assert replies == [
            MsRankingInfoOut(
                (
                    RankingEntry(0, 1, "Ana", 500, clan.id),
                    RankingEntry(1, 1, "Bia", 500, 0),
                    RankingEntry(2, 3, "Cai", 300, 0),
                )
            )
        ]


async def test_170_sem_login_nao_responde(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        replies = await RankingHandlers(SqlRankingRepository(db)).get_ranking(_session(None), b"")

        assert replies == []
