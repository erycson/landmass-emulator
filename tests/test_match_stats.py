"""Tempo jogado por jogador: regra pura de `with_played`, sem IO."""

from datetime import UTC, datetime, timedelta

from landmass_emu.domain.match_stats import MatchRecord, PlayerMatchStats, with_played

INICIO = datetime(2026, 10, 13, 22, 0, tzinfo=UTC)


def _partida() -> MatchRecord:
    jogadores = (
        PlayerMatchStats(account_id=7, nickname="Ana", slot=0, team=None, is_master=True),
        PlayerMatchStats(account_id=9, nickname="Bia", slot=1, team=None, is_master=False),
    )
    return MatchRecord(
        room_id=2,
        map_record_id=0,
        map_file="ONS-Treino",
        game_mode=0,
        game_class="XGame.LM_DeathMatch",
        team_count=0,
        max_players=4,
        time_limit=10,
        goal_score=80,
        started_at=INICIO,
        ended_at=INICIO,
        end_reason="",
        players=jogadores,
    )


def test_quem_nao_saiu_joga_ate_o_fim_e_quem_saiu_para_na_hora_da_saida() -> None:
    fim = INICIO + timedelta(seconds=600)

    partida = with_played(_partida(), {9: INICIO + timedelta(seconds=150)}, fim)

    ana, bia = partida.players
    assert (ana.played_seconds, ana.played_percent) == (600, 100.0)
    assert (bia.played_seconds, bia.played_percent) == (150, 25.0)
    assert partida.ended_at == fim


def test_saida_depois_do_fim_nao_passa_do_fim_e_partida_sem_duracao_zera() -> None:
    partida = with_played(_partida(), {9: INICIO + timedelta(seconds=900)}, INICIO)

    assert [p.played_seconds for p in partida.players] == [0, 0]
    assert [p.played_percent for p in partida.players] == [0.0, 0.0]
