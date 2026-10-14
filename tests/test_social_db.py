"""Repositório de amizades e bloqueios sobre SQLite real: a migração cria `friends` e `blocks`."""

from pathlib import Path

from landmass_emu.app import open_accounts, open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.social import SqlSocialRepository
from landmass_emu.domain.account import hash_token
from landmass_emu.ports.social import Contact, Relation
from landmass_emu.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
    )


async def test_amizade_e_bloqueio_sao_relacoes_dirigidas_e_separadas(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_database(settings) as db:
        accounts = SqlAccountRepository(db)
        ana = await accounts.create("ana", "Ana", hash_token("a" * 32))
        bia = await accounts.create("bia", "Bia", hash_token("b" * 32))
        social = SqlSocialRepository(db)

        assert await social.add(Relation.FRIEND, ana.id, bia.id) is True
        assert await social.add(Relation.FRIEND, ana.id, bia.id) is False  # par único
        assert await social.has(Relation.FRIEND, ana.id, bia.id)
        assert not await social.has(Relation.FRIEND, bia.id, ana.id)  # dirigida
        assert not await social.has(Relation.BLOCK, ana.id, bia.id)  # relação separada

        assert await social.contacts(Relation.FRIEND, ana.id) == (Contact(bia.id, "Bia", 0),)
        assert await social.contacts(Relation.BLOCK, ana.id) == ()

        assert await social.remove(Relation.FRIEND, ana.id, bia.id) is True
        assert await social.remove(Relation.FRIEND, ana.id, bia.id) is False
        assert await social.contacts(Relation.FRIEND, ana.id) == ()


async def test_contas_persistem_entre_aberturas_do_banco(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana = await accounts.create("ana", "Ana", hash_token("a" * 32))
        bia = await accounts.create("bia", "Bia", hash_token("b" * 32))
    async with open_database(settings) as db:
        await SqlSocialRepository(db).add(Relation.BLOCK, ana.id, bia.id)
    async with open_database(settings) as db:
        assert await SqlSocialRepository(db).has(Relation.BLOCK, ana.id, bia.id)
