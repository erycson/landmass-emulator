"""Registros que o cliente lê do canal, montados a partir do lobby e das salas.

Um lugar só para a montagem: sala (302, 141, 314), jogador do canal (151, 121) e jogador da sala
(317). O nick sai do lobby; o restante sai das regras de sala (`domain/rooms.py`).
"""

from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.rooms import Room
from landmass_emu.protocol.channel import (
    CsChannelPlayer,
    CsRoom,
    CsRoomPlayer,
    CsRoomPlayerInfoOut,
)


class ChannelRecords:
    def __init__(self, lobby: Lobby) -> None:
        self._lobby = lobby

    def room(self, room: Room) -> CsRoom:
        return CsRoom(
            room_id=room.room_id,
            name=room.name,
            has_password=bool(room.password),
            state=room.state,
            game_mode=room.game_mode,
            team_count=room.team_count,
            curr_player=len(room.members),
            max_player=room.max_player,
            map_num=room.map_num,
            limit_score=room.limit_score,
            limit_time=room.limit_time,
            master=room.master,
            slots=room.slot_guids(),
            scale=room.scale,
        )

    def lobby_players(self) -> tuple[CsChannelPlayer, ...]:
        """Todos do lobby, na ordem de entrada, cada um com o nick da conta."""
        return tuple(
            CsChannelPlayer(client_guid=guid, nick=nick) for guid, nick in self._lobby.players()
        )

    def room_players(self, room: Room) -> CsRoomPlayerInfoOut:
        return CsRoomPlayerInfoOut(
            tuple(
                CsRoomPlayer(
                    client_guid=guid,
                    slot=member.slot,
                    ready=member.ready,
                    morats=member.morats,
                    nick=self._lobby.nickname_of(guid) or "",
                )
                for guid, member in room.members.items()
            )
        )
