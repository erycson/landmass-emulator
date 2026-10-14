"""CLI de clãs (F13) sobre SQLite real: criar, entrar, sair, renomear, marcar e mostrar."""

from pathlib import Path

import pytest

from landmass_emu.admin_clan import ClanAdmin
from landmass_emu.app import open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.clans import SqlClanRepository
from landmass_emu.domain.account import hash_token
from landmass_emu.domain.clan import ClanError, ClanRules
from landmass_emu.ports.clans import ClanConflict
from landmass_emu.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
    )


async def test_fluxo_de_criar_entrar_renomear_marcar_e_mostrar(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts = SqlAccountRepository(db)
        admin = ClanAdmin(accounts, SqlClanRepository(db), ClanRules())
        await accounts.create("ana", "Ana", hash_token("a" * 32))
        await accounts.create("bia", "Bia", hash_token("b" * 32))

        assert await admin.create("Nova", "ana", 3) == "clã Nova criado (id 1); mestre Ana"
        assert await admin.join("bia", "Nova", 1) == "Bia entrou em Nova (grau 1)"
        assert await admin.rename("Nova", "Velha") == "clã Nova renomeado para Velha"
        assert await admin.mark("Velha", 9) == "marca de Velha definida como 9"

        texto = await admin.show("Velha")
        assert "marca 9" in texto
        assert "Ana grau 0" in texto
        assert "Bia grau 1" in texto


async def test_mestre_nao_sai_com_membros_e_clan_vazio_some(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts = SqlAccountRepository(db)
        clans = SqlClanRepository(db)
        admin = ClanAdmin(accounts, clans, ClanRules())
        await accounts.create("ana", "Ana", hash_token("a" * 32))
        await accounts.create("bia", "Bia", hash_token("b" * 32))
        await admin.create("Nova", "ana", 0)
        await admin.join("bia", "Nova", 0)

        with pytest.raises(ClanError, match="mestre"):
            await admin.leave("ana")

        await admin.leave("bia")
        assert await admin.leave("ana") == "Ana saiu de Nova; clã apagado (sem membros)"
        assert await clans.by_name("Nova") is None


async def test_erros_de_negocio_nao_gravam(tmp_path: Path) -> None:
    async with open_database(_settings(tmp_path)) as db:
        accounts = SqlAccountRepository(db)
        clans = SqlClanRepository(db)
        admin = ClanAdmin(accounts, clans, ClanRules())
        await accounts.create("ana", "Ana", hash_token("a" * 32))
        await accounts.create("bia", "Bia", hash_token("b" * 32))

        with pytest.raises(ClanError, match="não existe"):
            await admin.create("Nova", "ninguem", 0)
        with pytest.raises(ClanError, match="1 a 16"):
            await admin.create("", "ana", 0)
        await admin.create("Nova", "ana", 0)
        with pytest.raises(ClanConflict):
            await admin.join("ana", "Nova", 0)  # já tem clã
        with pytest.raises(ClanError, match="não tem clã"):
            await admin.leave("bia")
        bia = await accounts.find_by_username("bia")
        assert bia is not None
        assert await clans.by_account(bia.id) is None
