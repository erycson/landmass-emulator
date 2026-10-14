"""Parser do bloco `GameEnded` (hosting/game_end.py). O primeiro texto é o bloco real da primeira
partida com dois clientes (sala 2, TDM, ONS-AirPort, 2026-10-13), copiado do log da janela."""

from landmass_emu.hosting.game_end import GameEndedPlayer, parse_game_ended

LOG_REAL = """\
GameEnded: Game Reward Constant - wdb imported
GameEnded:   PCRoomBonusExp = 1.00
GameEnded:   DM_TakePoint = 1.00
Warning: LM_TeamGame (Function XGame.LM_DeathMatch.ControlEndReason:002E) Accessed None 'Winner'
GameEnded: XGame.LM_TeamGame Ended Deathmatch Exp/Money ==============================
GameEnded:     Player           = Tester2
GameEnded:     Reason           = TimeLimit
GameEnded:     NumPlayers       = 1
GameEnded:     MaxPlayers       = 24
GameEnded:     LimitKills       = 80
GameEnded:     Ranking          = 1
GameEnded:     Kills            = 0
GameEnded:     MaxKills         = 0.00
GameEnded:     Played           = 100.00%
GameEnded:     TotalExp         = 0
GameEnded:     TotalMoney       = 0
GameEnded: ==============================================================
Log: Socket close at UNetConnection::Tick by TimeOut
"""


def test_cabecalho_com_a_classe_do_lmemu_tambem_casa() -> None:
    # Com o pacote LMEmu (D190) o nome da classe no cabeçalho muda; o parser não depende dele.
    texto = LOG_REAL.replace("XGame.LM_TeamGame Ended", "LMEmu.LMEmuDeathMatch Ended")

    [jogador] = parse_game_ended(texto)

    assert jogador.nickname == "Tester2"


def test_bloco_real_da_primeira_partida_com_dois_clientes() -> None:
    [jogador] = parse_game_ended(LOG_REAL)

    assert jogador == GameEndedPlayer(
        nickname="Tester2",
        reason="TimeLimit",
        kills=0,
        ranking=1,
        played_percent=100.0,
        total_exp=0,
        total_money=0,
        winner=None,
        mission_score=None,
    )


def test_constantes_sem_bloco_nao_geram_jogador() -> None:
    texto = "GameEnded:   DM_TakePoint = 1.00\nGameEnded:   DM_WinPoint = 1.00\n"

    assert parse_game_ended(texto) == ()


def test_bloco_incompleto_sem_fechamento_e_ignorado() -> None:
    # Processo derrubado no meio da escrita do bloco: sem a linha de fechamento não há resultado.
    cortado = LOG_REAL.split("GameEnded: ====")[0]

    assert parse_game_ended(cortado) == ()


def test_le_um_bloco_por_jogador_e_vale_o_ultimo_do_mesmo_apelido() -> None:
    # O LM escreve um bloco por jogador (headless com 4 bots: 4 cabeçalhos seguidos).
    # Apelido repetido (fim escrito duas vezes): vale o último.
    primeiro = LOG_REAL.replace("Tester2", "Ana").replace(
        "Kills            = 0", "Kills            = 7"
    )
    segundo = """\
GameEnded: XGame.LM_TeamGame Ended Deathmatch Exp/Money ==============================
GameEnded:     Player           = Ana
GameEnded:     Reason           = LastMan
GameEnded:     Ranking          = 1
GameEnded:     Kills            = 12
GameEnded:     Played           = 62.50%
GameEnded:     TotalExp         = 3340.6
GameEnded:     TotalMoney       = 1710
GameEnded: ==============================================================
GameEnded: XGame.LM_TeamGame Ended Deathmatch Exp/Money ==============================
GameEnded:     Player           = Bia
GameEnded:     Ranking          = 2
GameEnded:     Kills            = 3
GameEnded:     Played           = 40.00%
GameEnded:     TotalExp         = 510
GameEnded:     TotalMoney       = 260
GameEnded: ==============================================================
"""

    jogadores = parse_game_ended(primeiro + segundo)

    assert [(j.nickname, j.ranking, j.kills) for j in jogadores] == [("Ana", 1, 12), ("Bia", 2, 3)]
    assert jogadores[0].total_exp == 3341  # float do log arredondado para inteiro
    assert jogadores[0].played_percent == 62.5
    assert jogadores[1].total_money == 260


def test_bloco_de_operacao_traz_vencedor_e_pontuacao_de_missao() -> None:
    texto = """\
GameEnded: XGame.LM_TeamOperation Ended TeamOperation Exp/Money ==============================
GameEnded:     Player           = Caio
GameEnded:     Reason           = Mission
GameEnded:     Winner           = True
GameEnded:     Kills            = 5
GameEnded:     MissionScore     = 12
GameEnded:     Played           = 37.50%
GameEnded:     TotalExp         = 800
GameEnded:     TotalMoney       = 420
GameEnded: ==============================================================
"""

    [caio] = parse_game_ended(texto)

    assert (caio.winner, caio.mission_score, caio.played_percent) == (True, 12, 37.5)
    assert (caio.total_exp, caio.total_money) == (800, 420)


def test_bot_vem_da_flag_do_lmemu_nao_do_apelido() -> None:
    # D252: o bloco não diz quem é bot; a linha `LMEmu: bot no fim` (flag bBot do PRI) diz.
    bot = LOG_REAL.replace("Player           = Tester2", "Player           = Saber")
    texto = LOG_REAL + bot + "ScriptLog: LMEmu: bot no fim Saber\n"

    jogadores = parse_game_ended(texto)

    assert [(j.nickname, j.bot) for j in jogadores] == [("Tester2", False), ("Saber", True)]
