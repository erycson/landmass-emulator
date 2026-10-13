"""Montagem do Channel Server (`ChannelHandlers`) e dos registros do canal (`ChannelRecords`)."""

from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.rooms import Rooms
from landmass_emu.domain.session_keys import MemorySessionKeyRegistry
from landmass_emu.handlers.channel import ChannelHandlers
from landmass_emu.handlers.channel.records import ChannelRecords
from landmass_emu.handlers.channel.rooms import GameEndpoint
from landmass_emu.protocol.channel import CsOp
from landmass_emu.protocol.progression import CsProgressionOp


class _Recebedor:
    """Destino de corpos: guarda o que recebe. Satisfaz `domain.lobby.Recipient`."""

    def __init__(self) -> None:
        self.corpos: list[bytes] = []

    def send(self, body: bytes) -> None:
        self.corpos.append(body)


def test_tabela_do_roteador_cobre_entrada_chat_salas_e_listas() -> None:
    # As opções não são usadas na montagem; o teste só confere as chaves do roteador.
    handlers = ChannelHandlers(
        MemorySessionKeyRegistry(), Lobby(), Rooms(), None, None, GameEndpoint("127.0.0.1", 7777)
    )
    esperados = {
        CsOp.HEARTBEAT,
        CsOp.IN_CHANNEL_SERVER,
        CsOp.IN_CHANNEL,
        CsOp.OUT_CHANNEL,
        CsOp.SEND_MESSAGE,
        CsOp.SAVE_OPTION,
        CsOp.CREATE_ROOM,
        CsOp.IN_ROOM,
        CsOp.OUT_ROOM,
        CsOp.READY_GAME,
        CsOp.CHANGE_ROOM_SLOT,
        CsOp.EXPEL_PLAYER,
        CsOp.REFRESH_PLAYER_LIST,
        CsOp.REFRESH_ROOM_LIST,
        CsProgressionOp.TUTORIAL_CLEAR,
    }
    assert esperados <= set(handlers.router)


def test_registros_do_lobby_na_ordem_de_entrada_com_nick() -> None:
    lobby = Lobby()
    lobby.join(7, _Recebedor(), "Ana")
    lobby.join(9, _Recebedor(), "Bia")
    jogadores = ChannelRecords(lobby).lobby_players()
    assert [(j.client_guid, j.nick) for j in jogadores] == [(7, "Ana"), (9, "Bia")]


def test_jogadores_da_sala_levam_o_nick_do_lobby_e_o_registro_de_sala() -> None:
    lobby = Lobby()
    lobby.join(7, _Recebedor(), "Ana")
    lobby.join(9, _Recebedor(), "Bia")
    rooms = Rooms()
    sala = rooms.create(
        7,
        name="Sala Azul",
        password="",
        scale=0,
        game_mode=1,
        map_num=1,
        max_player=4,
        team_count=1,
        limit_time=10,
        limit_score=10,
    )
    rooms.join(sala.room_id, 9, "")
    records = ChannelRecords(lobby)
    jogadores = records.room_players(sala).players
    assert [(j.client_guid, j.nick, j.slot) for j in jogadores] == [(7, "Ana", 0), (9, "Bia", 1)]
    registro = records.room(sala)
    assert registro.curr_player == 2
    assert registro.has_password is False
