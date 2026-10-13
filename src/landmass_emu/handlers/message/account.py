"""Opcodes de conta: 100 Login, 110 Register, 120 InMessageServer (exigem login, exceto 100)."""

import logging
from collections.abc import Sequence

from landmass_emu.domain.account import hash_token, verify_token
from landmass_emu.net.server import Reply
from landmass_emu.net.session import Session
from landmass_emu.ports.accounts import AccountRepository
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
    account = await accounts.find_by_token_hash(hash_token(req.login_num))
    if account is None or not verify_token(req.login_num, account.token_hash):
        log.info("[%s] login recusado", session.peer)
        return [MsLoginOut(MsResult.INVALID_PASSWORD)]
    session.account = account
    log.info("[%s] login de %s", session.peer, account.user_id)
    return [MsLoginOut(MsResult.OK)]


async def register(session: Session, payload: bytes) -> Sequence[Reply]:
    if session.account is None:
        log.warning("[%s] Register antes do login; ignorado", session.peer)
        return []
    return [MsRegisterOut()]


async def in_message_server(session: Session, payload: bytes) -> Sequence[Reply]:
    if session.account is None:
        log.warning("[%s] InMessageServer antes do login; ignorado", session.peer)
        return []
    return [MsInMessageServerOut(MsResult.OK, session.account.nickname)]
