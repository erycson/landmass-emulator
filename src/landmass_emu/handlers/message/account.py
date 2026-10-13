"""Opcodes de conta: 100 Login, 110 Register, 120 InMessageServer (exigem login, exceto 100)."""

import logging
from collections.abc import Sequence

from landmass_emu.handlers.login import login_by_token
from landmass_emu.net.server import Reply
from landmass_emu.net.session import Session
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.session_keys import SessionKeyRegistry
from landmass_emu.protocol.message import (
    MsInMessageServerOut,
    MsLoginIn,
    MsLoginOut,
    MsRegisterOut,
    MsResult,
)

log = logging.getLogger(__name__)


async def login(accounts: AccountRepository, session: Session, payload: bytes) -> Sequence[Reply]:
    # Só o fluxo por token: id/pw são ignorados até a senha ser implementada (D8, argon2id).
    req = MsLoginIn.unpack(payload)
    session.account = None
    account = await login_by_token(accounts, req.login_num)
    if account is None:
        log.info("[%s] login recusado", session.peer)
        return [MsLoginOut(MsResult.INVALID_PASSWORD)]
    session.account = account
    log.info("[%s] login de %s", session.peer, account.username)
    return [MsLoginOut(MsResult.OK)]


async def register(
    sessions: SessionKeyRegistry, session: Session, payload: bytes
) -> Sequence[Reply]:
    if session.account is None:
        log.warning("[%s] Register antes do login; ignorado", session.peer)
        return []
    return [MsRegisterOut(session_key=sessions.issue(session.account))]


async def in_message_server(session: Session, payload: bytes) -> Sequence[Reply]:
    if session.account is None:
        log.warning("[%s] InMessageServer antes do login; ignorado", session.peer)
        return []
    return [MsInMessageServerOut(MsResult.OK, session.account.nickname)]
