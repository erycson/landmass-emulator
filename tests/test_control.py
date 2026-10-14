"""Arquivo de controle (D203): gravação atômica, reivindicação única e o comando `shutdown`."""

import asyncio
import time
from argparse import Namespace
from pathlib import Path

import pytest

from landmass_emu.__main__ import Cli
from landmass_emu.control import discard_request, take_request, write_request
from landmass_emu.settings import Settings


def test_pedido_vai_e_volta_com_a_hora_de_saida(tmp_path: Path) -> None:
    arquivo = tmp_path / "control" / "shutdown.json"
    antes = time.time()
    write_request(arquivo, 300, "Manutenção.")
    pedido = take_request(arquivo)
    assert pedido is not None
    assert pedido.message == "Manutenção."
    assert antes + 299 <= pedido.at <= time.time() + 300


def test_pedido_e_consumido_uma_vez(tmp_path: Path) -> None:
    arquivo = tmp_path / "shutdown.json"
    write_request(arquivo, 10, "")
    assert take_request(arquivo) is not None
    assert take_request(arquivo) is None
    assert not arquivo.exists()
    assert not arquivo.with_name("shutdown.json.lido").exists()


def test_escrita_nao_deixa_temporario(tmp_path: Path) -> None:
    arquivo = tmp_path / "shutdown.json"
    write_request(arquivo, 10, "x")
    assert arquivo.exists()
    assert not arquivo.with_name("shutdown.json.tmp").exists()


def test_pedido_invalido_e_descartado_sem_derrubar(tmp_path: Path) -> None:
    arquivo = tmp_path / "shutdown.json"
    arquivo.write_text("{não é json", encoding="utf-8")
    assert take_request(arquivo) is None
    assert not arquivo.exists()


def test_descarte_e_seguro_sem_arquivo(tmp_path: Path) -> None:
    arquivo = tmp_path / "shutdown.json"
    discard_request(arquivo)  # não existe: sem erro
    write_request(arquivo, 10, "")
    discard_request(arquivo)
    assert not arquivo.exists()


def test_comando_grava_o_pedido_e_recusa_entrada_invalida(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, control_file=tmp_path / "shutdown.json")
    cli = Cli(settings)

    saida = cli.agenda_desligamento(Namespace(segundos=300, message="Oi"))
    assert "saída em 300 s" in saida
    assert take_request(settings.control_file) is not None

    with pytest.raises(ValueError, match="fora da faixa"):
        cli.agenda_desligamento(Namespace(segundos=-1, message=""))
    with pytest.raises(ValueError, match="passa de 80 bytes"):
        cli.agenda_desligamento(Namespace(segundos=10, message="x" * 81))
    assert not settings.control_file.exists()


async def test_serve_sai_quando_o_pedido_chega_com_o_lobby_vazio(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
        bind_host="127.0.0.1",
        message_port=0,
        channel_port=0,
        client_dir=tmp_path,
        control_file=tmp_path / "shutdown.json",
    )
    servidor = asyncio.create_task(Cli(settings).serve())
    await asyncio.sleep(0)  # o serve descarta pedidos antigos ao subir: escreve depois disso
    write_request(settings.control_file, 0, "")
    async with asyncio.timeout(10):
        await servidor
    assert not settings.control_file.exists()
