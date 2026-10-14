import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, inspect, select, update

from landmass_emu.__main__ import _parser
from landmass_emu.admin import AccountAdmin
from landmass_emu.app import open_accounts, open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.clans import SqlClanRepository
from landmass_emu.db.models import AccountRow
from landmass_emu.db.options import SqlOptionsRepository
from landmass_emu.domain.account import Account, hash_token, is_banned, new_token, verify_token
from landmass_emu.domain.presence import MessagePresence
from landmass_emu.domain.session_keys import MemorySessionKeyRegistry
from landmass_emu.handlers.message.account import AccountHandlers
from landmass_emu.net.session import Session
from landmass_emu.protocol.message import MsLoginIn, MsResult
from landmass_emu.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
        client_dir=tmp_path,
    )


def _sync_engine(tmp_path: Path) -> Engine:
    return create_engine(f"sqlite:///{tmp_path.as_posix()}/landmass.db")


def test_token_cabe_em_login_num() -> None:
    for _ in range(200):
        token = new_token()
        assert len(token) <= 32
        assert MsLoginIn.unpack(MsLoginIn(login_num=token).pack()).login_num == token


def test_hash_ignora_caixa_e_espacos() -> None:
    assert hash_token(" ABCDEF ") == hash_token("abcdef")
    assert verify_token("ABCDEF", hash_token("abcdef"))
    assert not verify_token("abcdef0", hash_token("abcdef"))


def _token_do_bat(bat: Path) -> str:
    match = re.search(r"login_num=([0-9a-f]+)", bat.read_text(encoding="ascii"))
    assert match is not None
    return match.group(1)


async def test_cria_conta_regenera_token_e_grava_bat(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        bat = await AccountAdmin(accounts, settings).create("fulano", "Fulano", tmp_path)
        token = _token_do_bat(bat)
        assert bat.name == "jogar_fulano.bat"
        raw = bat.read_bytes()
        assert raw.count(b"\n") == raw.count(b"\r\n") > 0
        assert b"login_server=127.0.0.1:7313?version=1245776779?login_num=" in raw
        account = await accounts.find_by_username("fulano")
        assert account is not None and account.nickname == "Fulano"
        assert verify_token(token, account.token_hash)

        with pytest.raises(ValueError, match="já existe"):
            await AccountAdmin(accounts, settings).create("fulano", "Outro", tmp_path)

        await AccountAdmin(accounts, settings).rotate_token("fulano", tmp_path)
        novo = _token_do_bat(bat)
        assert novo != token
        account = await accounts.find_by_username("fulano")
        assert account is not None
        assert verify_token(novo, account.token_hash)
        assert not verify_token(token, account.token_hash)


async def test_rejeita_usuario_invalido_e_pasta_inexistente(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        with pytest.raises(ValueError, match="usuário"):
            await AccountAdmin(accounts, settings).create("..\\x", "Nick", tmp_path)
        with pytest.raises(ValueError, match="usuário"):
            await AccountAdmin(accounts, settings).create("Fulano", "Nick", tmp_path)
        with pytest.raises(ValueError, match="diretório"):
            await AccountAdmin(accounts, settings).create("fulano", "Nick", tmp_path / "nao_existe")
        assert await accounts.find_by_username("fulano") is None


async def test_schema_segue_convencao_laravel(tmp_path: Path) -> None:
    async with open_accounts(_settings(tmp_path)):
        pass
    engine = _sync_engine(tmp_path)
    try:
        insp = inspect(engine)
        assert "accounts" in insp.get_table_names()
        colunas = [c["name"] for c in insp.get_columns("accounts")]
        assert colunas == [
            "id",
            "username",
            "nickname",
            "token_hash",
            "created_at",
            "updated_at",
            "tutorial_clear",
            "total_exp",
            "ld",
            "cash",
            "regular_nest_id",
            "regular_morat_class",
            "banned_until",
            "record_reset_at",
            "combat_reset_at",
        ]
        unicos = sorted(u["name"] for u in insp.get_unique_constraints("accounts"))
        assert unicos == [
            "accounts_nickname_unique",
            "accounts_token_hash_unique",
            "accounts_username_unique",
        ]
    finally:
        engine.dispose()


async def test_rotacao_atualiza_updated_at(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    antigo = datetime(2000, 1, 1)
    async with open_accounts(settings) as accounts:
        await AccountAdmin(accounts, settings).create("fulano", "Fulano", tmp_path)
    engine = _sync_engine(tmp_path)
    try:
        with engine.begin() as conn:
            conn.execute(update(AccountRow).values(updated_at=antigo))
        async with open_accounts(settings) as accounts:
            await AccountAdmin(accounts, settings).rotate_token("fulano", tmp_path)
        with engine.connect() as conn:
            atualizado = conn.scalar(select(AccountRow.updated_at))
    finally:
        engine.dispose()
    assert atualizado is not None and atualizado > antigo


def test_bloqueio_vale_so_ate_o_prazo() -> None:
    agora = datetime(2026, 10, 13, 12, tzinfo=UTC)
    conta = Account(id=1, username="fulano", nickname="Fulano", token_hash="h")
    assert not is_banned(conta, agora)
    assert is_banned(replace(conta, banned_until=agora + timedelta(seconds=1)), agora)
    assert not is_banned(replace(conta, banned_until=agora), agora)


def test_cli_de_ban_e_unban_leem_os_argumentos() -> None:
    args = _parser().parse_args(["account", "ban", "--user", "fulano", "--days", "3"])
    assert (args.action, args.user, args.days) == ("ban", "fulano", 3)
    assert _parser().parse_args(["account", "unban", "--user", "fulano"]).action == "unban"


async def _resultado_login(handlers: AccountHandlers, token: str) -> int:
    [resposta] = await handlers.login(Session(peer="teste"), MsLoginIn(login_num=token).pack())
    return resposta.result


async def test_ban_recusa_o_login_ate_expirar_e_unban_libera(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_database(settings) as db:
        accounts = SqlAccountRepository(db)
        admin = AccountAdmin(accounts, settings)
        bat = await admin.create("fulano", "Fulano", tmp_path)
        token = _token_do_bat(bat)
        handlers = AccountHandlers(
            accounts,
            MemorySessionKeyRegistry(),
            SqlOptionsRepository(db),
            MessagePresence(),
            SqlClanRepository(db),
        )
        with pytest.raises(ValueError, match="mínimo de 1 dia"):
            await admin.ban("fulano", 0)
        assert "bloqueada" in await admin.ban("fulano", 2)
        assert await _resultado_login(handlers, token) == MsResult.INVALID_PASSWORD
        # O prazo vence sozinho: sem nenhuma ação, o login volta a valer.
        conta = await accounts.find_by_username("fulano")
        assert conta is not None and conta.banned_until is not None
        await accounts.set_banned_until(conta.id, datetime.now(UTC) - timedelta(seconds=1))
        assert await _resultado_login(handlers, token) == MsResult.OK
        await admin.ban("fulano", 1)
        assert await _resultado_login(handlers, token) == MsResult.INVALID_PASSWORD
        assert "bloqueio removido" in await admin.unban("fulano")
        assert await _resultado_login(handlers, token) == MsResult.OK
