import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.admin import ProgressionAdmin
from landmass_emu.app import open_accounts, open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.catalog import WdbCatalog
from landmass_emu.db.progression import SqlProgressionRepository
from landmass_emu.domain.account import hash_token
from landmass_emu.domain.progression import MAX_I32, Grant, Progression, ProgressionService
from landmass_emu.settings import Settings

TOKEN_ANA = "0123456789abcdef0123456789abcdef"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
        client_dir=tmp_path,
    )


def _admin(db: async_sessionmaker[AsyncSession], catalog: Path) -> ProgressionAdmin:
    return ProgressionAdmin(
        SqlAccountRepository(db),
        SqlProgressionRepository(db),
        ProgressionService(),
        WdbCatalog(catalog),
    )


async def _conta_ana(settings: Settings) -> int:
    async with open_accounts(settings) as accounts:
        return (await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))).id


async def test_conta_nova_comeca_com_progressao_zerada(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    ana = await _conta_ana(settings)
    async with open_database(settings) as db:
        assert await SqlProgressionRepository(db).get(ana) == Progression()


async def test_grant_soma_nos_saldos_e_na_exp(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    ana = await _conta_ana(settings)
    async with open_database(settings) as db:
        repo = SqlProgressionRepository(db)
        await repo.grant(ana, Grant(exp=2800, ld=1000))
        await repo.grant(ana, Grant(exp=100, cash=500))
        assert await repo.get(ana) == Progression(total_exp=2900, ld=1000, cash=500)


async def test_marcar_tutorial_liga_bits_sem_perder_nenhum(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    ana = await _conta_ana(settings)
    async with open_database(settings) as db:
        repo = SqlProgressionRepository(db)
        assert (await repo.mark_tutorial(ana, 1)).tutorial_clear == 1
        assert (await repo.mark_tutorial(ana, 4)).tutorial_clear == 5
        assert (await repo.mark_tutorial(ana, 1)).tutorial_clear == 5  # idempotente
        # Passos concorrentes da mesma conta: o OR no banco não perde bit.
        await asyncio.gather(*(repo.mark_tutorial(ana, bit) for bit in (2, 1, 4)))
        assert (await repo.get(ana)).tutorial_clear == 7


async def test_tutorial_e_saldo_sao_independentes(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    ana = await _conta_ana(settings)
    async with open_database(settings) as db:
        repo = SqlProgressionRepository(db)
        await repo.mark_tutorial(ana, 2)
        await repo.grant(ana, Grant(ld=300))
        assert await repo.get(ana) == Progression(ld=300, tutorial_clear=2)


async def test_admin_grant_grava_e_informa_a_patente(
    tmp_path: Path, wdb_de_teste: Callable[[], Path]
) -> None:
    settings = _settings(tmp_path)
    await _conta_ana(settings)
    async with open_database(settings) as db:
        admin = _admin(db, wdb_de_teste())
        texto = await admin.grant("ana", Grant(exp=2800, ld=1000))
        assert texto == "ana: exp 2800, LD 1000, Cash 0. patente Praça (nível 2)"
        texto = await admin.grant("ana", Grant(cash=500))
        assert texto == "ana: exp 2800, LD 1000, Cash 500. patente Praça (nível 2)"


async def test_admin_grant_sem_wdb_grava_e_avisa_sem_patente(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    ana = await _conta_ana(settings)
    async with open_database(settings) as db:
        texto = await _admin(db, tmp_path / "sem_wdb.wdb").grant("ana", Grant(exp=10))
        assert "patente indisponível" in texto
        assert (await SqlProgressionRepository(db).get(ana)).total_exp == 10


async def test_admin_grant_conta_inexistente_e_limite_nao_gravam(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    ana = await _conta_ana(settings)
    async with open_database(settings) as db:
        admin = _admin(db, tmp_path / "sem_wdb.wdb")
        with pytest.raises(ValueError, match="não existe"):
            await admin.grant("bia", Grant(exp=1))
        await SqlProgressionRepository(db).grant(ana, Grant(exp=MAX_I32))
        with pytest.raises(ValueError, match="passa de"):
            await admin.grant("ana", Grant(exp=1))
        assert (await SqlProgressionRepository(db).get(ana)).total_exp == MAX_I32
