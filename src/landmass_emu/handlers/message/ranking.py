"""Ranking no Message Server (F14): 170 (GetRankingInfo) responde 171 com o top 100 por `total_exp`.

Empate divide a posição (1, 1, 3), e o índice do slot segue a ordem da lista (D56). Ranking por
nest não existe: 170 não tem corpo e 171 não tem campo de nest (dúvida 22).
"""

import logging
from collections.abc import Sequence

from landmass_emu.domain.ranking import MAX_RANKING_ROWS, RankingRules
from landmass_emu.net.server import Reply
from landmass_emu.net.session import Session
from landmass_emu.ports.ranking import RankingRepository
from landmass_emu.protocol.message import MsRankingInfoOut, RankingEntry

log = logging.getLogger(__name__)

_CLAN_MAX = 0xFFFF  # o siClan de 171 é u16


class RankingHandlers:
    def __init__(self, ranking: RankingRepository) -> None:
        self._ranking = ranking
        self._rules = RankingRules()

    async def get_ranking(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if session.account is None:
            log.warning("[%s] GetRankingInfo antes do login; ignorado", session.peer)
            return []
        rows = await self._ranking.top(MAX_RANKING_ROWS)
        entries = tuple(
            RankingEntry(
                position.index,
                position.rank,
                position.account.nickname,
                position.account.total_exp,
                # shortcut: clã acima de 65535 sai como 0 em 171 (u16), revisar se houver tantos.
                position.account.clan_id if position.account.clan_id <= _CLAN_MAX else 0,
            )
            for position in self._rules.positions(rows)
        )
        return [MsRankingInfoOut(entries)]
