"""Opcodes de conta: 100 Login, 110 Register, 120 InMessageServer (exigem login, exceto 100)."""

import logging
from collections.abc import Sequence

from landmass_emu.domain.account import Account, hash_token, verify_token
from landmass_emu.domain.presence import MessagePresence
from landmass_emu.net.server import Reply
from landmass_emu.net.session import Session
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.clans import ClanRepository
from landmass_emu.ports.options import OptionsRepository
from landmass_emu.ports.session_keys import SessionKeyRegistry
from landmass_emu.protocol.message import (
    MsInMessageServerOut,
    MsLoginIn,
    MsLoginOut,
    MsRegisterOut,
    MsResult,
)

log = logging.getLogger(__name__)


class AccountHandlers:
    def __init__(
        self,
        accounts: AccountRepository,
        sessions: SessionKeyRegistry,
        options: OptionsRepository,
        presence: MessagePresence,
        clans: ClanRepository,
    ) -> None:
        self._accounts = accounts
        self._sessions = sessions
        self._options = options
        self._presence = presence
        self._clans = clans

    async def login(self, session: Session, payload: bytes) -> Sequence[Reply]:
        # Só o fluxo por token: id/pw são ignorados até a senha ser implementada (D8, argon2id).
        req = MsLoginIn.unpack(payload)
        self._presence.unbind(session)  # re-login ou troca de conta na mesma conexão
        session.account = None
        account = await self._authenticate(req.login_num)
        if account is None:
            log.info("[%s] login recusado", session.peer)
            return [MsLoginOut(MsResult.INVALID_PASSWORD)]
        session.account = account
        self._presence.bind(account.id, session)
        log.info("[%s] login de %s", session.peer, account.username)
        return [MsLoginOut(MsResult.OK)]

    async def register(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if session.account is None:
            log.warning("[%s] Register antes do login; ignorado", session.peer)
            return []
        saved = await self._options.get(session.account.id)
        return [MsRegisterOut(options=saved, session_key=self._sessions.issue(session.account))]

    async def in_message_server(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if session.account is None:
            log.warning("[%s] InMessageServer antes do login; ignorado", session.peer)
            return []
        # clan_code > 0 faz o cliente pedir a lista e os membros do clã (features §0.1, §7).
        clan = await self._clans.by_account(session.account.id)
        clan_code = 0 if clan is None else clan.id
        return [MsInMessageServerOut(MsResult.OK, session.account.nickname, clan_code)]

    async def _authenticate(self, token: str) -> Account | None:
        """Login por token (`login_num`). O Channel usa a chave de sessão, não isto."""
        account = await self._accounts.find_by_token_hash(hash_token(token))
        if account is None or not verify_token(token, account.token_hash):
            return None
        return account
