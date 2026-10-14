"""CLI `account access` (D193) sobre SQLite real: grava o nível sem trocar o token, recusa faixa
fora de u8 e conta inexistente, e grava a troca na auditoria. Banco e auditoria em `tmp_path`."""

import json
from pathlib import Path

import pytest

from landmass_emu.__main__ import Cli, _parser
from landmass_emu.app import open_accounts
from landmass_emu.domain.account import hash_token, new_token
from landmass_emu.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
        client_dir=tmp_path,
        audit_log=tmp_path / "audit.jsonl",
    )


async def _conta(settings: Settings) -> str:
    """Cria a conta `bia` e devolve o hash do token gravado."""
    token_hash = hash_token(new_token())
    async with open_accounts(settings) as accounts:
        await accounts.create("bia", "Bia", token_hash)
    return token_hash


async def _comando(settings: Settings, *argumentos: str) -> str:
    args = _parser().parse_args(["account", "access", *argumentos])
    return await Cli(settings).account(args)


async def test_access_grava_nivel_sem_trocar_o_token(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    token_hash = await _conta(settings)

    saida = await _comando(settings, "bia", "9")

    assert "nível de acesso 9" in saida
    async with open_accounts(settings) as accounts:
        conta = await accounts.find_by_username("bia")
    assert conta is not None
    assert conta.access_level == 9
    assert conta.token_hash == token_hash  # `account token` invalidaria o login; este não


async def test_access_recusa_fora_de_u8_sem_mexer_na_conta(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    await _conta(settings)

    for nivel in ("256", "-1"):
        with pytest.raises(ValueError, match="de 0 a 255"):
            await _comando(settings, "bia", nivel)

    async with open_accounts(settings) as accounts:
        conta = await accounts.find_by_username("bia")
    assert conta is not None
    assert conta.access_level == 0


async def test_access_de_conta_inexistente_e_recusado(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(ValueError, match="não existe"):
        await _comando(settings, "ninguem", "9")


async def test_access_registra_a_troca_na_auditoria(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    await _conta(settings)

    await _comando(settings, "bia", "9")

    texto = settings.audit_log.read_text(encoding="utf-8")
    linhas = [json.loads(linha) for linha in texto.splitlines()]
    trocas = [linha for linha in linhas if linha["event"] == "gm_access"]
    assert trocas[-1]["nickname"] == "Bia"  # sem sessão, a auditoria grava o nick, não o usuário
    assert trocas[-1]["before"] == 0
    assert trocas[-1]["after"] == 9
