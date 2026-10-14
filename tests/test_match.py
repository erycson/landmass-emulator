"""Partida sem processo: plano (domínio), linha de comando, tabela UDP do Windows, catálogo de mapas
(`landmass.wdb`) e validação das settings do servidor de partida."""

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from landmass_emu.db.catalog import WdbCatalog
from landmass_emu.domain.match import (
    GAME_DEATHMATCH,
    GAME_OPERATION,
    GAME_TEAM,
    MapRecord,
    MatchPlan,
    build_plan,
    game_class_for,
)
from landmass_emu.domain.rooms import Room
from landmass_emu.hosting.command import build_command, match_url, udp_listeners
from landmass_emu.settings import Settings


def _sala(**campos: int) -> Room:
    base = {
        "room_id": 1,
        "name": "Sala",
        "password": "",
        "scale": 0,
        "game_mode": 0,
        "map_num": 1,
        "max_player": 8,
        "team_count": 2,
        "limit_time": 10,
        "limit_score": 20,
        "master": 7,
    }
    base.update(campos)
    return Room(**base)  # type: ignore[arg-type]


def test_modo_da_ui_vira_classe_do_jogo() -> None:
    assert game_class_for(1, 1) == GAME_OPERATION
    assert game_class_for(0, 2) == GAME_TEAM
    assert game_class_for(0, 1) == GAME_DEATHMATCH
    assert game_class_for(2, 2) == GAME_DEATHMATCH


def test_plano_limita_jogadores_ao_mapa_e_ao_minimo_de_dois() -> None:
    mapa = MapRecord(record_id=1, file_name="ONS-Treino", player_max=32, op_type=0)

    plano = build_plan(_sala(max_player=40), mapa)

    assert plano == MatchPlan("ONS-Treino", GAME_TEAM, 32, 10, 20)
    assert build_plan(_sala(max_player=1), mapa).max_players == 2


def test_linha_de_comando_leva_a_porta_antes_do_login() -> None:
    plano = MatchPlan("ONS-Treino", GAME_DEATHMATCH, 8, 10, 20)

    argv = build_command(
        Path("LandMass.exe"),
        plano,
        port=7801,
        message_addr="127.0.0.1:7313",
        version=123,
        login_num="abc",
    )

    assert argv[1] == match_url(plano)
    assert match_url(plano) == (
        "ONS-Treino?listen?game=XGame.LM_DeathMatch?MaxPlayers=8?TimeLimit=10?GoalScore=20"
    )
    assert argv[2:] == [
        "-server",
        "PORT=7801",
        "-log",
        "login_server=127.0.0.1:7313?version=123?login_num=abc",
    ]


def test_tabela_udp_traz_porta_e_pid_e_ignora_o_resto() -> None:
    texto = (
        "\nConexões Ativas\n\n"
        "  Proto  Endereço Local          Endereço Externo       Estado           PID\n"
        "  UDP    0.0.0.0:7777           *:*                                    208240\n"
        "  UDP    [::]:7777              *:*                                    208240\n"
        "  TCP    0.0.0.0:7314           0.0.0.0:0              LISTENING        1234\n"
    )

    assert udp_listeners(texto) == {(7777, 208240)}


def test_catalogo_acha_o_mapa_pelo_recordindex_que_e_texto(
    wdb_de_teste: Callable[[], Path],
) -> None:
    catalogo = WdbCatalog(wdb_de_teste())

    assert catalogo.get(1) == MapRecord(
        record_id=1, file_name="ONS-Treino", player_max=32, op_type=0
    )
    assert catalogo.get(9) is None


def test_catalogo_sem_arquivo_levanta_valueerror(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="não encontrado"):
        WdbCatalog(tmp_path / "nao_existe.wdb").get(1)


def test_sem_pasta_do_servidor_a_partida_e_o_endereco_fixo() -> None:
    settings = Settings(_env_file=None)

    assert settings.match_server_dir is None


def test_pasta_do_servidor_exige_login_num(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="LANDMASS_MATCH_LOGIN_NUM"):
        Settings(_env_file=None, match_server_dir=tmp_path)


def test_faixa_de_portas_invertida_e_recusada() -> None:
    with pytest.raises(ValidationError, match="PORT_MIN"):
        Settings(_env_file=None, match_port_min=7900, match_port_max=7800)
