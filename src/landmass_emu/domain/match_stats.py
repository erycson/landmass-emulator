"""Histórico de partida em memória. Regras puras, sem IO.

Métricas `None` quando o jogo não produz o dado (ver 04-persistence, "Histórico de partidas")."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PlayerMatchStats:
    account_id: int
    nickname: str
    slot: int
    team: int | None
    is_master: bool
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    ranking: int | None = None
    played_percent: float | None = None  # 0 a 100
    played_seconds: int | None = None
    won: bool | None = None
    headshots: int | None = None
    bullets: int | None = None
    hits: int | None = None
    damage: int | None = None
    exp: int | None = None
    money: int | None = None


@dataclass(frozen=True, slots=True)
class MatchRecord:
    room_id: int
    map_record_id: int
    map_file: str
    game_mode: int
    game_class: str
    team_count: int
    max_players: int
    time_limit: int
    goal_score: int
    started_at: datetime
    ended_at: datetime
    end_reason: str
    players: tuple[PlayerMatchStats, ...]
    uuid: str | None = None


def with_played(
    record: MatchRecord, left_at: dict[int, datetime], ended_at: datetime
) -> MatchRecord:
    """Preenche o tempo jogado de cada jogador: do início até a saída da partida (500, volta à sala
    ou saída da sala) ou até o fim. Quem não saiu joga até o fim. O percentual é do tempo da
    partida. Derivado pelo canal; não é o `Played` do bloco `GameEnded`."""
    duration = (ended_at - record.started_at).total_seconds()
    players = []
    for player in record.players:
        end = min(left_at.get(player.account_id, ended_at), ended_at)
        played = max((end - record.started_at).total_seconds(), 0.0)
        percent = round(played * 100 / duration, 2) if duration > 0 else 0.0
        players.append(
            replace(player, played_seconds=int(played), played_percent=min(percent, 100.0))
        )
    return replace(record, ended_at=ended_at, players=tuple(players))


@dataclass(frozen=True, slots=True)
class GameEndedPlayer:
    """Um jogador do bloco `GameEnded` do log do servidor de partida (re/game_server_host.md §11.4).
    O `Played` do log não entra no histórico: o tempo jogado vem do canal (`with_played`)."""

    nickname: str
    reason: str | None
    kills: int | None
    ranking: int | None
    played_percent: float | None  # 0 a 100, como o log escreve ("100.00%")
    total_exp: int | None
    total_money: int | None
    winner: bool | None  # só OP e time: `Winner` do bloco
    mission_score: int | None  # só OP: `MissionScore`


def with_game_end(record: MatchRecord, jogadores: Iterable[GameEndedPlayer]) -> MatchRecord:
    """Leva kills, colocação, exp e LD do bloco para cada jogador, pelo nick. Quem não aparece no
    bloco fica como está (None): sem dado, sem recompensa."""
    por_nick = {j.nickname: j for j in jogadores}
    players = []
    for player in record.players:
        j = por_nick.get(player.nickname)
        if j is None:
            players.append(player)
            continue
        players.append(
            replace(
                player,
                kills=j.kills,
                ranking=j.ranking,
                won=player.won if j.winner is None else j.winner,
                exp=j.total_exp,
                money=j.total_money,
            )
        )
    return replace(record, players=tuple(players))
