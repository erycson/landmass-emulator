"""Operações de conta da CLI: cria conta, regenera token e grava o `.bat` de login do jogador."""

from pathlib import Path

from landmass_emu.domain.account import check_nickname, check_username, hash_token, new_token
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.settings import Settings


class AccountAdmin:
    def __init__(self, accounts: AccountRepository, settings: Settings) -> None:
        self._accounts = accounts
        self._settings = settings

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
