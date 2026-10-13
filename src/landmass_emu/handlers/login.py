"""Autenticação por token (`login_num`) do Message (100). O Channel usa a chave de sessão."""

from landmass_emu.domain.account import Account, hash_token, verify_token
from landmass_emu.ports.accounts import AccountRepository


async def login_by_token(accounts: AccountRepository, token: str) -> Account | None:
    account = await accounts.find_by_token_hash(hash_token(token))
    if account is None or not verify_token(token, account.token_hash):
        return None
    return account
