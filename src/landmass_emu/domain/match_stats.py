"""Histórico de partida em memória. Regras puras, sem IO.

Métricas `None` quando o jogo não produz o dado (ver 04-persistence, "Histórico de partidas")."""

from dataclasses import dataclass
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
