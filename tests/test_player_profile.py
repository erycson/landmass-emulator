"""Ficha do jogador (542/543) sobre SQLite real: posição com empate (D18), partidas só com
resultado (D105), clã e nest (D107)."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import update

from landmass_emu.app import open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.clans import SqlClanRepository
from landmass_emu.db.matches import SqlMatchRepository
from landmass_emu.db.models import AccountRow
from landmass_emu.db.profile import SqlPlayerProfileRepository
from landmass_emu.db.ranking import SqlRankingRepository
from landmass_emu.domain.account import hash_token
from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.match_stats import MatchRecord, PlayerMatchStats
from landmass_emu.domain.ranking import RankingRules
from landmass_emu.domain.rooms import Rooms
from landmass_emu.handlers.channel.lists import ListHandlers
from landmass_emu.handlers.channel.records import ChannelRecords
from landmass_emu.net.session import Session
from landmass_emu.protocol.channel import CsPlayerDetailOut
from landmass_emu.protocol.message import cfield
from landmass_emu.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
    )


def _jogador(account_id: int, nick: str, slot: int, **metricas: Any) -> PlayerMatchStats:
    return PlayerMatchStats(
        account_id=account_id,
        nickname=nick,
        slot=slot,
        team=None,
        is_master=slot == 0,
        **metricas,
    )


def _partida(*jogadores: PlayerMatchStats) -> MatchRecord:
    agora = datetime(2026, 10, 13, 12, tzinfo=UTC)
    return MatchRecord(
        room_id=1,
        map_record_id=1,
        map_file="ONS-Treino",
        game_mode=0,
        game_class="XGame.LM_TeamGame",
        team_count=2,
        max_players=8,
        time_limit=10,
        goal_score=30,
        started_at=agora,
        ended_at=agora,
        end_reason="exit_play",
        players=jogadores,
    )


async def test_posicao_empata_na_menor_e_bate_com_o_ranking(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts = SqlAccountRepository(db)
        ids = [
            (await accounts.create(nome, nome.title(), hash_token(nome * 32))).id
            for nome in ("ana", "bia", "cai")
        ]
        async with db.begin() as session:
            for account_id, exp in zip(ids, (500, 500, 100), strict=True):
                await session.execute(
                    update(AccountRow).where(AccountRow.id == account_id).values(total_exp=exp)
                )
        perfis = SqlPlayerProfileRepository(db)
        assert (await perfis.profile(ids[0])).rank == 1
        assert (await perfis.profile(ids[1])).rank == 1
        assert (await perfis.profile(ids[2])).rank == 3
        assert await perfis.profile(999) is None

        # A posição da ficha é a mesma que o ranking (171) mostra para cada conta.
        posicoes = RankingRules().positions(await SqlRankingRepository(db).top(100))
        for posicao in posicoes:
            perfil = await perfis.profile(posicao.account.account_id)
            assert perfil is not None and perfil.rank == posicao.rank


async def test_partida_so_conta_com_resultado_e_quem_nao_terminou_fica_sem_vitoria(
    tmp_path: Path,
) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts = SqlAccountRepository(db)
        ana = await accounts.create("ana", "Ana", hash_token("a" * 32))
        bia = await accounts.create("bia", "Bia", hash_token("b" * 32))
        cai = await accounts.create("cai", "Cai", hash_token("c" * 32))
        matches = SqlMatchRepository(db)
        # Com resultado: Ana venceu e Bia saiu sem `won` (não terminou).
        await matches.save(
            _partida(
                _jogador(ana.id, "Ana", 0, won=True, kills=3, deaths=1, headshots=1),
                _jogador(bia.id, "Bia", 1, won=None, kills=2, deaths=2),
            )
        )
        # Sem nenhum resultado: não conta para jogos, mas abates entram.
        await matches.save(
            _partida(_jogador(ana.id, "Ana", 0, kills=4), _jogador(cai.id, "Cai", 1))
        )
        perfis = SqlPlayerProfileRepository(db)
        ana_perfil = await perfis.profile(ana.id)
        assert ana_perfil is not None
        assert (ana_perfil.games, ana_perfil.wins, ana_perfil.losses) == (1, 1, 0)
        assert (ana_perfil.kills, ana_perfil.deaths, ana_perfil.headshots) == (7, 1, 1)
        bia_perfil = await perfis.profile(bia.id)
        assert bia_perfil is not None
        assert (bia_perfil.games, bia_perfil.wins, bia_perfil.losses) == (1, 0, 0)
        cai_perfil = await perfis.profile(cai.id)
        assert cai_perfil is not None
        assert (cai_perfil.games, cai_perfil.wins, cai_perfil.losses) == (0, 0, 0)


async def test_ficha_traz_clan_e_nest_da_conta(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts = SqlAccountRepository(db)
        ana = await accounts.create("ana", "Ana", hash_token("a" * 32))
        bia = await accounts.create("bia", "Bia", hash_token("b" * 32))
        await SqlClanRepository(db).create("Alfa", ana.id, 7)
        await accounts.set_regular(ana.id, 2, 1)
        perfis = SqlPlayerProfileRepository(db)
        ana_perfil = await perfis.profile(ana.id)
        assert ana_perfil is not None
        assert (ana_perfil.clan_name, ana_perfil.clan_mark, ana_perfil.nest) == ("Alfa", 7, 2)
        bia_perfil = await perfis.profile(bia.id)
        assert bia_perfil is not None
        assert (bia_perfil.clan_name, bia_perfil.clan_mark, bia_perfil.nest) == ("", 0, 0)


async def test_542_monta_o_543_com_a_ficha_do_banco(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts = SqlAccountRepository(db)
        ana = await accounts.create("ana", "Ana", hash_token("a" * 32))
        await SqlClanRepository(db).create("Alfa", ana.id, 7)
        await accounts.set_regular(ana.id, 2, 1)
        await SqlMatchRepository(db).save(
            _partida(
                _jogador(ana.id, "Ana", 0, won=True, kills=3, deaths=1, headshots=1),
                _jogador(999, "Outro", 1, won=False),
            )
        )
        lobby = Lobby()
        sessao = Session(peer="ana")
        lobby.join(ana.id, sessao, "Ana", 0)
        listas = ListHandlers(lobby, Rooms(), ChannelRecords(lobby), SqlPlayerProfileRepository(db))
        [ficha] = await listas.player_detail(sessao, cfield("Ana", 17))
        assert ficha == CsPlayerDetailOut(
            nickname="Ana",
            rank=1,
            games=1,
            wins=1,
            losses=0,
            kills=3,
            deaths=1,
            headshots=1,
            total_exp=0,
            nest=2,
            clan_mark=7,
            clan="Alfa",
        )
