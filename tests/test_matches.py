from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, func, inspect, select
from sqlalchemy.exc import IntegrityError

from landmass_emu.app import open_accounts, open_database
from landmass_emu.db.matches import SqlMatchRepository
from landmass_emu.db.models import AccountRow, MatchPlayerRow, MatchRow
from landmass_emu.domain.account import hash_token
from landmass_emu.domain.match_stats import MatchRecord, PlayerMatchStats
from landmass_emu.settings import Settings

INICIO = datetime(2026, 10, 13, 20, 0, tzinfo=UTC)
TOKEN = "0123456789abcdef0123456789abcdef"
FIM = datetime(2026, 10, 13, 20, 12, tzinfo=UTC)
METRICAS = (
    "kills",
    "deaths",
    "assists",
    "ranking",
    "played_percent",
    "played_seconds",
    "won",
    "headshots",
    "bullets",
    "hits",
    "damage",
    "exp",
    "money",
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
        client_dir=tmp_path,
    )


def _sync_engine(tmp_path: Path) -> Engine:
    return create_engine(f"sqlite:///{tmp_path.as_posix()}/landmass.db")


def _partida(*jogadores: PlayerMatchStats) -> MatchRecord:
    return MatchRecord(
        room_id=3,
        map_record_id=12,
        map_file="ruins.lmm",
        game_mode=1,
        game_class="LM_DeathMatch",
        team_count=0,
        max_players=8,
        time_limit=600,
        goal_score=30,
        started_at=INICIO,
        ended_at=FIM,
        end_reason="goal",
        players=jogadores,
    )


async def test_save_grava_partida_e_jogadores_com_e_sem_metricas(tmp_path: Path) -> None:
    ana = PlayerMatchStats(
        account_id=1,
        nickname="Ana",
        slot=0,
        team=1,
        is_master=True,
        kills=7,
        deaths=2,
        assists=1,
        ranking=1,
        played_percent=87.5,
        won=True,
        exp=120,
        money=900,
    )
    bia = PlayerMatchStats(account_id=2, nickname="Bia", slot=1, team=None, is_master=False)
    async with open_database(_settings(tmp_path)) as db:
        match_id = await SqlMatchRepository(db).save(_partida(ana, bia))
        async with db() as session:
            partida = await session.get(MatchRow, match_id)
            jogadores = (
                await session.scalars(
                    select(MatchPlayerRow)
                    .where(MatchPlayerRow.match_id == match_id)
                    .order_by(MatchPlayerRow.slot)
                )
            ).all()

    assert partida is not None
    assert (partida.room_id, partida.map_file, partida.end_reason) == (3, "ruins.lmm", "goal")
    assert [j.nickname for j in jogadores] == ["Ana", "Bia"]
    gravada_ana, gravada_bia = jogadores
    assert [getattr(gravada_ana, m) for m in METRICAS] == [
        7,
        2,
        1,
        1,
        87.5,
        None,
        True,
        *[None] * 4,
        120,
        900,
    ]
    assert gravada_ana.team == 1
    assert all(getattr(gravada_bia, m) is None for m in METRICAS)
    assert gravada_bia.team is None


async def test_save_soma_exp_e_ld_do_bloco_na_mesma_transacao(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana_id = (await accounts.create("ana", "Ana", hash_token(TOKEN))).id
    ana = PlayerMatchStats(
        account_id=ana_id, nickname="Ana", slot=0, team=None, is_master=True, exp=3341, money=1710
    )
    # Bia não tem exp nem LD no bloco: não recebe nada, e a conta dela nem existe aqui.
    bia = PlayerMatchStats(
        account_id=ana_id + 1, nickname="Bia", slot=1, team=None, is_master=False
    )
    async with open_database(settings) as db:
        await SqlMatchRepository(db).save(_partida(ana, bia))
        async with db() as session:
            conta = await session.get(AccountRow, ana_id)

    assert (conta.total_exp, conta.ld) == (3341, 1710)


async def test_account_repetido_na_partida_e_recusado_pelo_banco(tmp_path: Path) -> None:
    primeiro = PlayerMatchStats(account_id=1, nickname="Ana", slot=0, team=None, is_master=True)
    repetido = PlayerMatchStats(account_id=1, nickname="Ana", slot=1, team=None, is_master=False)
    async with open_database(_settings(tmp_path)) as db:
        with pytest.raises(IntegrityError):
            await SqlMatchRepository(db).save(_partida(primeiro, repetido))
        # Transação única: a partida e o primeiro jogador também não ficam gravados.
        async with db() as session:
            assert await session.scalar(select(func.count(MatchRow.id))) == 0
            assert await session.scalar(select(func.count(MatchPlayerRow.id))) == 0


async def test_banco_migra_do_zero_com_as_tabelas_de_partida(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)):
        pass
    engine = _sync_engine(tmp_path)
    try:
        insp = inspect(engine)
        # Modelo e migração devem concordar: nomes, ordem, nulos e constraints.
        assert [c["name"] for c in insp.get_columns("matches")] == (
            MatchRow.__table__.columns.keys()
        )
        assert [c["name"] for c in insp.get_columns("match_players")] == (
            MatchPlayerRow.__table__.columns.keys()
        )
        nulos = {c["name"] for c in insp.get_columns("match_players") if c["nullable"]}
        assert nulos == {"team", *METRICAS}
        assert [u["name"] for u in insp.get_unique_constraints("match_players")] == [
            "match_players_match_id_account_id_unique"
        ]
        assert [fk["name"] for fk in insp.get_foreign_keys("match_players")] == [
            "match_players_match_id_foreign"
        ]
    finally:
        engine.dispose()
