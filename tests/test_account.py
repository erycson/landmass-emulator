import re
from pathlib import Path

import pytest

from landmass_emu import admin
from landmass_emu.app import open_accounts
from landmass_emu.domain.account import hash_token, new_token, verify_token
from landmass_emu.protocol.message import MsLoginIn
from landmass_emu.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
        client_dir=tmp_path,
    )


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
        bat = await admin.create_account(accounts, settings, "fulano", "Fulano", tmp_path)
        token = _token_do_bat(bat)
        assert bat.name == "jogar_fulano.bat"
        raw = bat.read_bytes()
        assert raw.count(b"\n") == raw.count(b"\r\n") > 0
        assert b"login_server=127.0.0.1:7313?version=1245776779?login_num=" in raw
        account = await accounts.find_by_user_id("fulano")
        assert account is not None and account.nickname == "Fulano"
        assert verify_token(token, account.token_hash)

        with pytest.raises(ValueError, match="já existe"):
            await admin.create_account(accounts, settings, "fulano", "Outro", tmp_path)

        await admin.rotate_token(accounts, settings, "fulano", tmp_path)
        novo = _token_do_bat(bat)
        assert novo != token
        account = await accounts.find_by_user_id("fulano")
        assert account is not None
        assert verify_token(novo, account.token_hash)
        assert not verify_token(token, account.token_hash)


async def test_rejeita_usuario_invalido_e_pasta_inexistente(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        with pytest.raises(ValueError, match="usuário"):
            await admin.create_account(accounts, settings, "..\\x", "Nick", tmp_path)
        with pytest.raises(ValueError, match="usuário"):
            await admin.create_account(accounts, settings, "Fulano", "Nick", tmp_path)
        with pytest.raises(ValueError, match="diretório"):
            await admin.create_account(
                accounts, settings, "fulano", "Nick", tmp_path / "nao_existe"
            )
        assert await accounts.find_by_user_id("fulano") is None
