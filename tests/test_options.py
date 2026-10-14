import asyncio
from dataclasses import fields, replace
from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, text

from landmass_emu.app import open_accounts, open_database
from landmass_emu.db.options import KeyBindDefaults, MouseDefaults, SqlOptionsRepository
from landmass_emu.domain.account import hash_token
from landmass_emu.protocol.message import LmRegisterInfo
from landmass_emu.settings import Settings

TOKEN_ANA = "0123456789abcdef0123456789abcdef"
TOKEN_BIA = "fedcba9876543210fedcba9876543210"
PADRAO = LmRegisterInfo(**KeyBindDefaults.VALUES, **MouseDefaults.VALUES)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
        client_dir=tmp_path,
    )


def _sync_engine(tmp_path: Path) -> Engine:
    return create_engine(f"sqlite:///{tmp_path.as_posix()}/landmass.db")


async def test_conta_sem_registro_devolve_padrao(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana = await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))
    async with open_database(settings) as db:
        assert await SqlOptionsRepository(db).get(ana.id) == PADRAO


async def test_save_insere_e_depois_substitui_as_37_opcoes(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana = await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))
    async with open_database(settings) as db:
        repo = SqlOptionsRepository(db)
        await repo.save(ana.id, LmRegisterInfo(background=1, weapon_1=2, screenshot=9))
        assert await repo.get(ana.id) == replace(PADRAO, background=1, weapon_1=2, screenshot=9)
        # Save substitui a linha inteira: campos fora do novo registro voltam ao padrão.
        await repo.save(ana.id, LmRegisterInfo(mouse_sensitivity=4))
        assert await repo.get(ana.id) == replace(PADRAO, mouse_sensitivity=4)
        # Sensibilidade gravada em 0 volta ao padrão no próximo 111; outras opções em 0 ficam.
        await repo.save(ana.id, LmRegisterInfo(mouse_sensitivity=0, mouse_invert=1))
        assert await repo.get(ana.id) == replace(PADRAO, mouse_invert=1)

    engine = _sync_engine(tmp_path)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM account_options")).scalar() == 1
            criado, atualizado = conn.execute(
                text("SELECT created_at, updated_at FROM account_options")
            ).one()
        assert datetime.fromisoformat(str(atualizado)) >= datetime.fromisoformat(str(criado))
    finally:
        engine.dispose()


async def test_saves_concorrentes_da_mesma_conta_nao_duplicam(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana = await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))
    async with open_database(settings) as db:
        repo = SqlOptionsRepository(db)
        await asyncio.gather(*(repo.save(ana.id, LmRegisterInfo(fire=i)) for i in range(1, 9)))
        assert (await repo.get(ana.id)).fire in range(1, 9)

    engine = _sync_engine(tmp_path)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM account_options")).scalar() == 1
    finally:
        engine.dispose()


async def test_opcoes_sao_por_conta_e_sobrevivem_a_reabertura(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana = await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))
        bia = await accounts.create("bia", "Bia", hash_token(TOKEN_BIA))
    async with open_database(settings) as db:
        await SqlOptionsRepository(db).save(ana.id, LmRegisterInfo(jump=3))
    async with open_database(settings) as db:
        repo = SqlOptionsRepository(db)
        assert await repo.get(ana.id) == replace(PADRAO, jump=3)
        assert await repo.get(bia.id) == PADRAO


async def test_tecla_gravada_em_zero_recebe_padrao_e_valor_gravado_fica(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana = await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))
    async with open_database(settings) as db:
        repo = SqlOptionsRepository(db)
        await repo.save(ana.id, LmRegisterInfo(move_forward=65))  # A no lugar de W
        opcoes = await repo.get(ana.id)
        assert opcoes.move_forward == 65
        assert opcoes.move_backward == KeyBindDefaults.VALUES["move_backward"]
        assert opcoes == replace(PADRAO, move_forward=65)


async def test_schema_account_options_segue_lm_register_info(tmp_path: Path) -> None:
    async with open_accounts(_settings(tmp_path)):
        pass
    engine = _sync_engine(tmp_path)
    try:
        insp = inspect(engine)
        colunas = [c["name"] for c in insp.get_columns("account_options")]
        nomes = [f.name for f in fields(LmRegisterInfo)]
        assert colunas == ["id", "account_id", *nomes, "created_at", "updated_at"]
        assert [u["name"] for u in insp.get_unique_constraints("account_options")] == [
            "account_options_account_id_unique"
        ]
        assert [fk["name"] for fk in insp.get_foreign_keys("account_options")] == [
            "account_options_account_id_foreign"
        ]
    finally:
        engine.dispose()
