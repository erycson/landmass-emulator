"""Operações da CLI sobre contas: cria conta, regenera token (grava o `.bat` de login) e
concede progressão (exp, LD, Cash).
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from landmass_emu.db.catalog import WdbCatalog
from landmass_emu.domain.account import (
    Account,
    check_nickname,
    check_username,
    hash_token,
    new_token,
)
from landmass_emu.domain.progression import Grant, ProgressionService, RankTable
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.progression import ProgressionRepository
from landmass_emu.settings import Settings


class AccountAdmin:
    def __init__(self, accounts: AccountRepository, settings: Settings) -> None:
        self._accounts = accounts
        self._settings = settings

    async def ban(self, username: str, days: int) -> str:
        """Bloqueio temporário (D106): recusa o login até o prazo. Sem aviso ao servidor (D27)."""
        if days < 1:
            raise ValueError("bloqueio: mínimo de 1 dia")
        account = await self._account(username)
        until = datetime.now(UTC) + timedelta(days=days)
        await self._accounts.set_banned_until(account.id, until)
        return f"{username} bloqueada até {until:%Y-%m-%d %H:%M} UTC (vale no próximo login)"

    async def unban(self, username: str) -> str:
        account = await self._account(username)
        await self._accounts.set_banned_until(account.id, None)
        return f"{username}: bloqueio removido"

    async def _account(self, username: str) -> Account:
        account = await self._accounts.find_by_username(username)
        if account is None:
            raise ValueError(f"conta {username!r} não existe")
        return account

    async def create(self, username: str, nickname: str, client_dir: Path) -> Path:
        check_username(username)
        check_nickname(nickname)
        self._check_client_dir(client_dir)
        if await self._accounts.find_by_username(username) is not None:
            raise ValueError(f"conta {username!r} já existe; use 'account token' para novo token")
        token = new_token()
        await self._accounts.create(username, nickname, hash_token(token))
        return self._write_launcher(client_dir, username, token)

    async def rotate_token(self, username: str, client_dir: Path) -> Path:
        check_username(username)
        self._check_client_dir(client_dir)
        account = await self._accounts.find_by_username(username)
        if account is None:
            raise ValueError(f"conta {username!r} não existe")
        token = new_token()
        await self._accounts.set_token_hash(account.id, hash_token(token))
        return self._write_launcher(client_dir, username, token)

    @staticmethod
    def _check_client_dir(client_dir: Path) -> None:
        if not client_dir.is_dir():
            raise ValueError(f"diretório do cliente não existe: {client_dir}")

    def _write_launcher(self, client_dir: Path, username: str, token: str) -> Path:
        """Grava `jogar_<user>.bat` (CRLF). O token é segredo: não é impresso."""
        settings = self._settings
        path = client_dir / f"jogar_{username}.bat"
        text = (
            "@echo off\n"
            'cd /d "%~dp0"\n'
            f'start "" LandMass.exe login_server={settings.public_host}:{settings.message_port}'
            f"?version={settings.client_version}?login_num={token}\n"
        )
        path.write_text(text, encoding="ascii", newline="\r\n")
        return path


class ProgressionAdmin:
    """Concessão de exp, LD e Cash pela CLI. Só grava no banco: um servidor rodando não é
    avisado (D27). O cliente vê os valores ao relogar, quando o 101 é montado de novo."""

    def __init__(
        self,
        accounts: AccountRepository,
        progression: ProgressionRepository,
        rules: ProgressionService,
        catalog: WdbCatalog,
    ) -> None:
        self._accounts = accounts
        self._progression = progression
        self._rules = rules
        self._catalog = catalog

    async def grant(self, username: str, grant: Grant) -> str:
        account = await self._accounts.find_by_username(username)
        if account is None:
            raise ValueError(f"conta {username!r} não existe")
        # Confere os limites antes de gravar: a soma passar de i32 quebraria o 101 do login.
        totals = self._rules.check_grant(await self._progression.get(account.id), grant)
        await self._progression.grant(account.id, grant)
        return (
            f"{username}: exp {totals.total_exp}, LD {totals.ld}, Cash {totals.cash}. "
            f"{self._rank_line(totals.total_exp)}"
        )

    def _rank_line(self, total_exp: int) -> str:
        try:
            level = RankTable(self._catalog.level_list()).level_for(total_exp)
        except ValueError as e:
            return f"patente indisponível: {e}"
        return f"patente {level.name} (nível {level.level})"
