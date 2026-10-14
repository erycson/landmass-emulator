"""Plano da partida: mapa, classe do jogo e limites a partir da sala. Só regras, sem IO.

Mapa: `RecordIndex` da tabela `maps` do `landmass.wdb` é o `map_num` da sala. Modo: a UI do cliente
(`XInterface`, `nModeIndex`) lê `game_mode == 1` como OP, `game_mode == 0` com dois times como time
e o resto como DM. As classes estão em `re/game_server_host.md`, seção 10. O time é
`XGame.LM_TeamDeathMatch` (D170).
"""

from dataclasses import dataclass

from landmass_emu.domain.rooms import Room

GAME_DEATHMATCH = "XGame.LM_DeathMatch"
# LM_TeamGame herda BecomeSpectator=false de LM_DeathMatch e trava o respawn em TDM (D170).
GAME_TEAM = "XGame.LM_TeamDeathMatch"
GAME_OPERATION = "XGame.LM_TeamOperation"
TEAM_COUNT_FOR_TEAM_GAME = 2
MIN_PLAYERS = 2


@dataclass(frozen=True, slots=True)
class MapRecord:
    """Linha da tabela `maps` do cliente, só com o que a partida usa."""

    record_id: int
    file_name: str  # MapFileName, sem extensão (ex.: ONS-Treino)
    player_max: int  # PlayerCountMax
    op_type: int


@dataclass(frozen=True, slots=True)
class MatchPlan:
    map_file: str
    game_class: str
    max_players: int
    time_limit: int  # limit_time da sala, em minutos (inferido pela UI; ver re/game_server_host.md)
    goal_score: int  # limit_score da sala


def game_class_for(game_mode: int, team_count: int) -> str:
    if game_mode == 1:
        return GAME_OPERATION
    if game_mode == 0 and team_count == TEAM_COUNT_FOR_TEAM_GAME:
        return GAME_TEAM
    return GAME_DEATHMATCH


def build_plan(room: Room, map_record: MapRecord) -> MatchPlan:
    # Limite de jogadores: o da sala, limitado pelo que o mapa comporta.
    max_players = min(max(room.max_player, MIN_PLAYERS), map_record.player_max)
    return MatchPlan(
        map_file=map_record.file_name,
        game_class=game_class_for(room.game_mode, room.team_count),
        max_players=max_players,
        time_limit=room.limit_time,
        goal_score=room.limit_score,
    )
