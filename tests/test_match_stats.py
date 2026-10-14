"""Tempo jogado por jogador: regra pura de `with_played`, sem IO."""

from datetime import UTC, datetime, timedelta

from landmass_emu.domain.match_stats import (
    GameEndedPlayer,
    MatchRecord,
    PlayerMatchStats,
    with_game_end,
    with_played,
)

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


def test_bloco_gameended_leva_kills_colocacao_exp_e_ld_pelo_nick() -> None:
    bloco = (
        GameEndedPlayer(
            nickname="Ana",
            reason="TimeLimit",
            kills=12,
            ranking=1,
            played_percent=62.5,
            total_exp=3341,
            total_money=1710,
            winner=None,
            mission_score=None,
        ),
    )

    ana, bia = with_game_end(_partida(), bloco).players

    assert (ana.kills, ana.ranking, ana.exp, ana.money) == (12, 1, 3341, 1710)
    assert ana.won is None  # DM não traz `Winner`: fica sem vencedor
    assert (bia.kills, bia.exp, bia.money) == (None, None, None)  # sem bloco, sem recompensa


def test_espectador_no_bloco_gameended_nao_entra_no_historico() -> None:
    # Espectador não está em `record.players` (D197): se o log citar o nick dele, nada muda.
    bloco = (
        GameEndedPlayer(
            nickname="Espec",
            reason="TimeLimit",
            kills=5,
            ranking=2,
            played_percent=100.0,
            total_exp=900,
            total_money=300,
            winner=None,
            mission_score=None,
        ),
    )

    resultado = with_game_end(_partida(), bloco)

    assert [p.nickname for p in resultado.players] == ["Ana", "Bia"]
    assert all(p.exp is None and p.money is None for p in resultado.players)


def test_bot_com_o_apelido_de_um_jogador_nao_leva_a_recompensa_dele() -> None:
    # D252: a recompensa casa pelo apelido, mas o bot (flag bBot) fica de fora mesmo com o
    # nome igual.
    bloco = (
        GameEndedPlayer(
            nickname="Ana",
            reason="TimeLimit",
            kills=30,
            ranking=1,
            played_percent=100.0,
            total_exp=9000,
            total_money=5000,
            winner=None,
            mission_score=None,
            bot=True,
        ),
    )

    ana, _ = with_game_end(_partida(), bloco).players

    assert (ana.kills, ana.exp, ana.money) == (None, None, None)
