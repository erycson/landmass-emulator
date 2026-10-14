import sqlite3
from pathlib import Path

import pytest

from landmass_emu.__main__ import Cli
from landmass_emu.settings import Settings
from landmass_emu.update.client import point_client

ESQUEMA = """
CREATE TABLE message_server (idx integer, name varchar(20), address varchar(16), port integer);
INSERT INTO message_server VALUES (0, 'MsgServer01', '201.77.211.176', 7313);
CREATE TABLE update_server (name varchar(50), "desc" varchar(50), address varchar(50),
  login_id varchar(20), password varchar(20), remote_path varchar(100), local_path varchar(100),
  port int, retry int, retry_delay int, use_firewall int, use_passive_mode int);
INSERT INTO update_server VALUES ('LM patch 01', 'Landmass Patch 01', 'ftp://201.76.37.107',
  'landmassbr', 'original', 'balance', '', 21, 3, 5, 0, 1);
"""


def _wdb(pasta: Path) -> Path:
    wdb = pasta / "landmass.wdb"
    con = sqlite3.connect(wdb)
    con.executescript(ESQUEMA)
    con.close()
    return wdb


def _aponta(wdb: Path, pasta: Path, host: str = "127.0.0.1", user: str = "jogador") -> None:
    point_client(
        wdb,
        pasta / "update",
        message_host=host,
        message_port=7313,
        update_host=host,
        update_port=7412,
        user=user,
        password="segredo",
    )


def test_aponta_as_duas_tabelas_guarda_original_e_cria_pasta(tmp_path: Path) -> None:
    wdb = _wdb(tmp_path)
    original = wdb.read_bytes()

    _aponta(wdb, tmp_path)

    con = sqlite3.connect(wdb)
    try:
        msg = con.execute("SELECT address, port FROM message_server").fetchall()
        upd = con.execute(
            "SELECT address, port, login_id, password, use_passive_mode, remote_path"
            " FROM update_server"
        ).fetchall()
    finally:
        con.close()
    assert msg == [("127.0.0.1", 7313)]
    assert upd == [("ftp://127.0.0.1", 7412, "jogador", "segredo", 1, "balance")]
    assert (wdb.with_name("landmass.wdb.antes-patch")).read_bytes() == original
    assert (tmp_path / "update" / "balance").is_dir()
    # D255: sem arquivo na listagem o Launcher acusa falha de conexão
    assert (tmp_path / "update" / "leia-me.txt").is_file()


def test_reaplicar_mantem_o_backup_original(tmp_path: Path) -> None:
    wdb = _wdb(tmp_path)
    original = wdb.read_bytes()

    _aponta(wdb, tmp_path, host="10.0.0.1")
    _aponta(wdb, tmp_path, host="127.0.0.1")

    assert wdb.with_name("landmass.wdb.antes-patch").read_bytes() == original


def test_senha_longa_recusa_sem_tocar_no_arquivo(tmp_path: Path) -> None:
    wdb = _wdb(tmp_path)
    original = wdb.read_bytes()

    with pytest.raises(ValueError, match="passam de 20 bytes"):
        point_client(
            wdb,
            tmp_path / "update",
            message_host="127.0.0.1",
            message_port=7313,
            update_host="127.0.0.1",
            update_port=7412,
            user="jogador",
            password="x" * 21,
        )
    assert wdb.read_bytes() == original
    assert not wdb.with_name("landmass.wdb.antes-patch").exists()


def test_wdb_ausente_levanta_erro(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="não encontrado"):
        _aponta(tmp_path / "nao_existe.wdb", tmp_path)


def test_comando_launcher_exige_porta_de_atualizacao(tmp_path: Path) -> None:
    _wdb(tmp_path)
    settings = Settings(client_dir=tmp_path, update_dir=tmp_path / "update")
    with pytest.raises(ValueError, match="LANDMASS_UPDATE_PORT"):
        Cli(settings).aponta_launcher()

    settings = Settings(
        client_dir=tmp_path, update_dir=tmp_path / "update", update_port=7412, update_user="j"
    )
    assert "ftp://127.0.0.1:7412" in Cli(settings).aponta_launcher()
    assert (tmp_path / "update" / "balance").is_dir()
