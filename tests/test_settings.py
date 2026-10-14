from pathlib import Path

import pytest
from pydantic import ValidationError

from landmass_emu.settings import Settings, load_settings

RAIZ = Path(__file__).resolve().parent.parent


def test_padroes_do_marco_1() -> None:
    s = Settings(_env_file=None)
    assert s.message_port == 7313 and s.channel_port == 7314
    assert s.recv_timeout == 300
    assert [(c.name, c.max_clients) for c in s.channels] == [("Canal 1", 100)]


def test_canais_vem_de_json_no_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANDMASS_CHANNELS", '[{"name": "Norte", "max_clients": 50}]')
    monkeypatch.setenv("LANDMASS_PUBLIC_HOST", "192.168.0.10")
    s = Settings(_env_file=None)
    assert [(c.name, c.max_clients) for c in s.channels] == [("Norte", 50)]
    assert s.public_host == "192.168.0.10"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"recv_timeout": 59},
        {"public_host": "x" * 16},
        {"channels": []},
        {"shutdown_notice_seconds": [60, 60]},
        {"shutdown_grace_seconds": -1},
    ],
)
def test_rejeita_valores_fora_do_protocolo(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **kwargs)


def test_avisos_de_desligamento_ficam_em_ordem_decrescente() -> None:
    s = Settings(_env_file=None, shutdown_notice_seconds=[10, 300, 60])
    assert s.shutdown_notice_seconds == [300, 60, 10]


def test_ambiente_vence_arquivo_e_arquivo_vence_padrao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    toml = tmp_path / "landmass.toml"
    toml.write_text("message_port = 8000\nrecv_timeout = 120\n", encoding="utf-8")
    monkeypatch.setenv("LANDMASS_MESSAGE_PORT", "9000")
    s = load_settings(toml)
    assert s.message_port == 9000  # ambiente
    assert s.recv_timeout == 120  # arquivo
    assert s.channel_port == 7314  # padrão


def test_le_arquivo_indicado_por_variavel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    toml = tmp_path / "landmass.toml"
    toml.write_text("bind_host = '10.0.0.5'\n", encoding="utf-8")
    monkeypatch.setenv("LANDMASS_CONFIG", str(toml))
    monkeypatch.delenv("LANDMASS_BIND_HOST", raising=False)
    assert load_settings().bind_host == "10.0.0.5"


def test_arquivo_informado_inexistente_e_erro(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="não existe"):
        load_settings(tmp_path / "nao-existe.toml")


def test_chave_desconhecida_no_arquivo_e_erro(tmp_path: Path) -> None:
    toml = tmp_path / "landmass.toml"
    toml.write_text("mesage_port = 9000\n", encoding="utf-8")  # typo de propósito
    with pytest.raises(ValueError, match="chaves desconhecidas: mesage_port"):
        load_settings(toml)


def test_segredo_lido_de_arquivo_sem_fim_de_linha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    segredo = tmp_path / "login_num"
    segredo.write_bytes(b"chave-de-teste\r\n")
    monkeypatch.setenv("LANDMASS_MATCH_LOGIN_NUM_FILE", str(segredo))
    monkeypatch.delenv("LANDMASS_MATCH_LOGIN_NUM", raising=False)
    s = Settings(_env_file=None)
    assert s.match_login_num == "chave-de-teste"


def test_segredo_com_variavel_e_arquivo_juntos_e_erro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    segredo = tmp_path / "login_num"
    segredo.write_text("x\n", encoding="utf-8")
    monkeypatch.setenv("LANDMASS_MATCH_LOGIN_NUM", "y")
    monkeypatch.setenv("LANDMASS_MATCH_LOGIN_NUM_FILE", str(segredo))
    with pytest.raises(ValueError, match="definidas juntas"):
        Settings(_env_file=None)


def test_segredo_ilegivel_nomeia_a_variavel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LANDMASS_DATABASE_URL_FILE", str(tmp_path / "sumiu"))
    monkeypatch.delenv("LANDMASS_DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="LANDMASS_DATABASE_URL_FILE: arquivo não lido"):
        Settings(_env_file=None)


def test_arquivo_de_exemplo_bate_com_os_padroes(monkeypatch: pytest.MonkeyPatch) -> None:
    """O `config.example.toml` lista os padrões: se um padrão mudar, o exemplo muda junto."""
    for nome in ("LANDMASS_CONFIG", "LANDMASS_MESSAGE_PORT", "LANDMASS_CHANNELS"):
        monkeypatch.delenv(nome, raising=False)
    exemplo = load_settings(RAIZ / "config.example.toml")
    padrao = Settings(_env_file=None)
    for campo in (
        "database_url",
        "bind_host",
        "public_host",
        "message_port",
        "channel_port",
        "client_version",
        "client_dir",
        "recv_timeout",
        "game_host",
        "game_port",
        "match_port_min",
        "match_port_max",
        "match_ready_timeout",
        "audit_log",
        "shutdown_grace_seconds",
        "shutdown_notice_seconds",
        "control_file",
        "log_level",
        "log_json",
    ):
        assert getattr(exemplo, campo) == getattr(padrao, campo), campo
    assert [(c.name, c.max_clients) for c in exemplo.channels] == [("Canal 1", 100)]
