"""Sonda de saúde (D204): conecta nas portas de escuta. Porta sem servidor é falha; durante o
desligamento a sonda segue verde, porque os listeners continuam abertos."""

import asyncio
import socket
from pathlib import Path

import pytest

from landmass_emu.__main__ import Cli
from landmass_emu.app import game_servers
from landmass_emu.health import HealthProbe
from landmass_emu.settings import Settings
from landmass_emu.shutdown import Shutdown


async def _fecha(_: asyncio.StreamReader, escrita: asyncio.StreamWriter) -> None:
    escrita.close()


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def test_servidores_no_ar_dao_saudavel() -> None:
    a = await asyncio.start_server(_fecha, "127.0.0.1", 0)
    b = await asyncio.start_server(_fecha, "127.0.0.1", 0)
    async with a, b:
        portas = (a.sockets[0].getsockname()[1], b.sockets[0].getsockname()[1])
        assert await HealthProbe("127.0.0.1", portas).failures() == []


async def test_porta_sem_servidor_e_falha_e_o_motivo_nomeia_a_porta() -> None:
    fechada = _porta_livre()
    async with await asyncio.start_server(_fecha, "127.0.0.1", 0) as s:
        aberta = s.sockets[0].getsockname()[1]
        falhas = await HealthProbe("127.0.0.1", (aberta, fechada)).failures()
    assert len(falhas) == 1
    assert f"porta {fechada}" in falhas[0]


async def test_bind_em_todas_as_interfaces_testa_o_loopback() -> None:
    async with await asyncio.start_server(_fecha, "127.0.0.1", 0) as s:
        porta = s.sockets[0].getsockname()[1]
        assert await HealthProbe("0.0.0.0", (porta,)).failures() == []


async def test_health_segue_verde_durante_o_desligamento(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
        bind_host="127.0.0.1",
        message_port=0,
        channel_port=0,
        client_dir=tmp_path,
    )
    desliga = Shutdown()
    async with game_servers(settings, desliga) as (msg, channel):
        portas = (msg.sockets[0].getsockname()[1], channel.sockets[0].getsockname()[1])
        desliga.begin(300)
        assert await HealthProbe("127.0.0.1", portas).failures() == []


async def test_comando_health_sai_com_erro_quando_uma_porta_cai(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        bind_host="127.0.0.1",
        message_port=_porta_livre(),
        channel_port=_porta_livre(),
        client_dir=tmp_path,
    )
    with pytest.raises(ValueError, match="fora do ar"):
        await Cli(settings).health()
