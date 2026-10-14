"""Ranking por `total_exp` (F14, 07-progression §4.10, D18). Sem IO.

Empate recebe a menor posição do grupo (1, 1, 3), como `usp_renew_ranking` do legado. Ranking por
nest não entra: 170 não tem corpo e 171 não tem campo de nest (dúvida 22)."""

from collections.abc import Sequence
from dataclasses import dataclass

MAX_RANKING_ROWS = 100  # o cliente lê no máximo 100 linhas (tools/re/protocol_full.md §2.2)


@dataclass(frozen=True, slots=True)
class RankedAccount:
    account_id: int
    nickname: str
    total_exp: int
    clan_id: int  # 0 sem clã


@dataclass(frozen=True, slots=True)
class RankedPosition:
    index: int  # slot do array do cliente, 0 a 99
    rank: int  # posição com empate na menor
    account: RankedAccount


class RankingRules:
    def positions(self, ordered: Sequence[RankedAccount]) -> tuple[RankedPosition, ...]:
        """`ordered` vem de `top()`: total_exp decrescente. Com corte em 100, a posição de cada
        linha só depende das linhas antes dela, então o corte não altera os empates visíveis."""
        out: list[RankedPosition] = []
        rank = 0
        previous: int | None = None
        for index, account in enumerate(ordered[:MAX_RANKING_ROWS]):
            if account.total_exp != previous:
                rank = index + 1
                previous = account.total_exp
            out.append(RankedPosition(index, rank, account))
        return tuple(out)
