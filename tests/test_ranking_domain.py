"""Regras de ranking (F14) sem IO: posição com empate na menor e corte em 100."""

from landmass_emu.domain.ranking import MAX_RANKING_ROWS, RankedAccount, RankingRules


def _conta(i: int, exp: int, clan: int = 0) -> RankedAccount:
    return RankedAccount(i, f"c{i}", exp, clan)


def test_empate_divide_a_menor_posicao() -> None:
    contas = [_conta(1, 500), _conta(2, 500), _conta(3, 300), _conta(4, 300), _conta(5, 100)]

    ranks = [p.rank for p in RankingRules().positions(contas)]

    assert ranks == [1, 1, 3, 3, 5]


def test_index_segue_a_ordem_da_lista() -> None:
    contas = [_conta(1, 500), _conta(2, 500), _conta(3, 300)]

    assert [p.index for p in RankingRules().positions(contas)] == [0, 1, 2]


def test_corte_em_100_linhas() -> None:
    contas = [_conta(i, 1000 - i) for i in range(MAX_RANKING_ROWS + 20)]

    posicoes = RankingRules().positions(contas)

    assert len(posicoes) == MAX_RANKING_ROWS
    assert posicoes[-1].index == MAX_RANKING_ROWS - 1


def test_empate_na_fronteira_do_corte_mantem_a_posicao() -> None:
    contas = [_conta(i, 1000) for i in range(MAX_RANKING_ROWS + 5)]

    assert {p.rank for p in RankingRules().positions(contas)} == {1}


def test_sem_contas_nao_ha_posicoes() -> None:
    assert RankingRules().positions([]) == ()
