"""Plano da partida: mapa, classe do jogo e limites a partir da sala. Só regras, sem IO.

Mapa: `RecordIndex` da tabela `maps` do `landmass.wdb` é o `map_num` da sala. Modo, como o servidor
nativo (`LM_Engine` `CServerRoom::Init`, `re/LM_Engine.dll/all/100163d0_Init.c`, linhas 317 a 363):
`game_mode == 1` é OP ou Bombing Run pelo `OPType` do mapa; `game_mode == 0` com dois ou mais times
é time; o resto é DM. As classes estão em `re/game_server_host.md`, seção 10. O time é
`XGame.LM_TeamDeathMatch` (D170), estendido pelo pacote LMEmu (D190). Regra do modo: D192.
"""

from dataclasses import dataclass

from landmass_emu.domain.rooms import MAX_SPECTATORS, Room

# Classes do pacote LMEmu (`unreal/build_lmemu.py`). Herdam das de XGame e leem o equipamento de
# cada jogador do `LMEmu.ini` pela chave `?lmemu=` (D190).
GAME_DEATHMATCH = "LMEmu.LMEmuDeathMatch"
# LM_TeamGame herda BecomeSpectator=false de LM_DeathMatch e trava o respawn em TDM (D170).
GAME_TEAM = "LMEmu.LMEmuTeamDeathMatch"
GAME_OPERATION = "LMEmu.LMEmuTeamOperation"
GAME_BOMBING = "LMEmu.LMEmuBombingRun"
# `OPType` do mapa que escolhe a classe de OP (D192). Os demais valores (ex.: Onslaught nativo) não
# têm classe LMEmu e caem em DM.
OP_TYPE_OPERATION = 0
OP_TYPE_BOMBING = 1
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
    # `?MaxSpectators=` da URL: o teto de espectadores da sala (D197).
    max_spectators: int = MAX_SPECTATORS
    # Valores `Players=` da seção do LMEmu.ini, uma linha por jogador (D190). Vazio se não há.
    loadout: tuple[str, ...] = ()
    # Chave da seção do LMEmu.ini (`?lmemu=`). Quem põe é o servidor de partida ao lançar.
    lmemu_key: str = ""
    # Bots da partida, limitados ao máximo da sala (D220): `?MinPlayers=` e uma linha `Bots=` cada.
    bots: int = 0
    # Linhas `chave=valor` da mesma seção além dos `Players=` (`Bots=`, `Owner=`; D220).
    loadout_extra: tuple[tuple[str, str], ...] = ()


def game_class_for(game_mode: int, team_count: int, op_type: int) -> str:
    if game_mode == 1:
        if op_type == OP_TYPE_BOMBING:
            return GAME_BOMBING
        if op_type == OP_TYPE_OPERATION:
            return GAME_OPERATION
        return GAME_DEATHMATCH
    if game_mode == 0 and team_count >= TEAM_COUNT_FOR_TEAM_GAME:
        return GAME_TEAM
    return GAME_DEATHMATCH


def build_plan(room: Room, map_record: MapRecord, bots: int = 0) -> MatchPlan:
    # Limite de jogadores: o da sala, limitado pelo que o mapa comporta.
    max_players = min(max(room.max_player, MIN_PLAYERS), map_record.player_max)
    return MatchPlan(
        map_file=map_record.file_name,
        game_class=game_class_for(room.game_mode, room.team_count, map_record.op_type),
        max_players=max_players,
        time_limit=room.limit_time,
        goal_score=room.limit_score,
        # Bot cabe na sala: o total da partida não passa do máximo de jogadores (D220).
        bots=min(bots, max_players),
    )
