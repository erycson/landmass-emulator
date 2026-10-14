"""Espectador de sala (D197): sem vaga de jogador, quem entra vai para um slot >= 60 (`MySlot >= 60`
no cliente), até `MAX_SPECTATORS`. Espectador não tem pronto nem grupo, não entra na partida e não
decide o início, o dono ou a configuração da sala."""

import pytest

from landmass_emu.domain.rooms import (
    MAX_SPECTATORS,
    ROOM_PLAYER_SLOTS,
    ROOM_PLAYING,
    RoomError,
    RoomReason,
    Rooms,
)
from landmass_emu.handlers.channel.rooms import _settings
from landmass_emu.protocol.channel import ROOM_FLAG_LIMIT_PLAYER, CsChangeRoomPropertyIn


def _sala(rooms: Rooms, owner: int = 1, max_player: int = 2) -> None:
    rooms.create(
        owner,
        name="Sala",
        password="",
        scale=0,
        game_mode=0,
        map_num=1,
        max_player=max_player,
        team_count=2,
        limit_time=10,
        limit_score=20,
    )


def test_sem_vaga_de_jogador_entra_espectador_ate_o_teto() -> None:
    rooms = Rooms()
    _sala(rooms, max_player=2)
    rooms.join(1, 2, "")  # segunda vaga de jogador

    assert rooms.join(1, 3, "").members[3].slot == ROOM_PLAYER_SLOTS
    assert rooms.join(1, 4, "").members[4].slot == ROOM_PLAYER_SLOTS + 1
    with pytest.raises(RoomError) as cheio:
        rooms.join(1, 5, "")
    assert cheio.value.reason is RoomReason.FULL


def test_teto_de_espectadores_e_o_do_servidor_de_partida() -> None:
    assert MAX_SPECTATORS == 2


def test_espectador_nao_fica_pronto_nem_troca_de_grupo() -> None:
    rooms = Rooms()
    _sala(rooms, max_player=2)
    rooms.join(1, 2, "")
    rooms.join(1, 3, "")

    with pytest.raises(RoomError) as pronto:
        rooms.toggle_ready(3, 0)
    assert pronto.value.reason is RoomReason.SPECTATOR
    with pytest.raises(RoomError) as grupo:
        rooms.change_slot(3, 1)
    assert grupo.value.reason is RoomReason.SPECTATOR


def test_inicio_ignora_espectador_e_ele_nao_entra_na_partida() -> None:
    rooms = Rooms()
    _sala(rooms, max_player=2)
    rooms.join(1, 2, "")
    rooms.join(1, 3, "")
    rooms.toggle_ready(2, 0)  # o espectador 3 não está pronto e não precisa estar

    partida = rooms.start(1, 0)

    assert partida.state == ROOM_PLAYING
    assert partida.in_game == {1, 2}


def test_sair_o_ultimo_jogador_leva_os_espectadores_junto() -> None:
    rooms = Rooms()
    _sala(rooms, max_player=2)
    rooms.join(1, 2, "")
    rooms.join(1, 3, "")
    rooms.leave(1)

    saida = rooms.leave(2)

    assert saida is not None and saida.removed
    assert saida.spectators == (3,)
    assert rooms.room_of(3) is None


def test_dono_que_sai_passa_para_jogador_e_nao_para_espectador() -> None:
    rooms = Rooms()
    _sala(rooms, max_player=2)
    rooms.join(1, 2, "")
    rooms.join(1, 3, "")  # sem vaga: espectador no slot 60
    rooms.leave(2)  # libera a vaga de jogador
    rooms.join(1, 4, "")  # quem entra agora é jogador; o espectador 3 fica antes na ordem

    saida = rooms.leave(1)

    assert saida is not None and saida.new_master == 4


def test_411_nao_passa_dos_slots_de_jogador() -> None:
    # Sem o limite, 70 põe um jogador no slot 60 e o cliente o trata como espectador.
    req = CsChangeRoomPropertyIn(
        flags=ROOM_FLAG_LIMIT_PLAYER,
        map_num=0,
        game_mode=0,
        team_count=0,
        max_player=70,
        limit_time=0,
        limit_score=0,
    )

    assert _settings(req)["max_player"] == ROOM_PLAYER_SLOTS


def test_configurar_max_player_nao_conta_espectador() -> None:
    rooms = Rooms()
    _sala(rooms, max_player=2)
    rooms.join(1, 2, "")
    rooms.join(1, 3, "")  # espectador no slot 60: não deve travar a configuração

    sala = rooms.configure(1, {"max_player": 2})

    assert sala.max_player == 2
