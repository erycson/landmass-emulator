import pytest
from pydantic import ValidationError

from landmass_emu.settings import Settings


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
    ],
)
def test_rejeita_valores_fora_do_protocolo(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **kwargs)
