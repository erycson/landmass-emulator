"""Comandos de GM do console: aviso (250 e 251) e expulsão (700 e 701). D193.

O cliente só mostra estes comandos a quem tem `ucAccess` 9 ou mais; o servidor confere de novo
com o nível fixado na entrada no canal (`Lobby.access_of`). Cada pedido aceito ou recusado vai à
auditoria (`EconomyAudit`).
"""

import logging
from collections.abc import Sequence

from landmass_emu.audit import EconomyAudit
from landmass_emu.domain.access import may_expel, may_notify
from landmass_emu.domain.lobby import Lobby
from landmass_emu.net.server import Reply, reply_body
from landmass_emu.net.session import Session
from landmass_emu.protocol.channel import (
    CsExpelPlayerIn,
    CsExpelPlayerOut,
    CsSendCommandIn,
    CsSendCommandOut,
)
from landmass_emu.protocol.header import CHANNEL_NET_CODE

log = logging.getLogger(__name__)

# `kind` do 700 (`FUN_10017bb0`). O emulador tem um canal só: WEB e CHANNEL e LOBBY expulsam da
# mesma forma (shortcut: sem sessão de web no emulador).
POS_WEB = 0x10
POS_CHANNEL = 0x21
POS_LOBBY = 0x22
EXPEL_KINDS = (POS_WEB, POS_CHANNEL, POS_LOBBY)

# Resultados do 701 (mesmos códigos de CERR em `re/layouts_f0.md` §7.3). A tela não mostra o 701,
# então o código fica só na auditoria e no log.
RESULT_EXPELLED = 0
ERR_TARGET_OFFLINE = -2460  # nick fora do canal (CERR_FIND_PLAYER, rooms.py)
ERR_NOT_ALLOWED = -4061  # nível insuficiente (CERR_INVITE_ROOM_NOT_ADMIN, rooms.py)


class GmHandlers:
    def __init__(self, lobby: Lobby, audit: EconomyAudit | None) -> None:
        self._lobby = lobby
        self._audit = audit

    async def send_command(self, session: Session, payload: bytes) -> Sequence[Reply]:
        """250 (`/NOTIFY` ou `/ALLNOTIFY`): o aviso vai a todo o lobby, quem mandou incluído."""
        guid = self._lobby.guid_of(session)
        if guid is None:
            log.warning("[%s] SendCommand fora do lobby; ignorado", session.peer)
            return []
        level = self._lobby.access_of(guid)
        req = CsSendCommandIn.unpack(payload)
        if not may_notify(level):
            log.warning("[%s] SendCommand sem nível de GM (%d); ignorado", session.peer, level)
            return []
        if not req.text:
            return []
        # shortcut: um canal só, então /ALLNOTIFY (todos os canais) e /NOTIFY (este canal) chegam
        # aos mesmos quadros. O bit `all_server` fica na auditoria para o dia em que houver mais.
        self._lobby.broadcast(reply_body(CsSendCommandOut(req.text), CHANNEL_NET_CODE))
        self._record(
            session,
            "gm_notice",
            all_server=req.all_server,
            text=req.text.decode("cp1252", errors="replace"),
        )
        return []

    async def expel_player(self, session: Session, payload: bytes) -> Sequence[Reply]:
        """700 (`/EXPEL`): tira o jogador do canal pelo nick. O 701 volta a quem pediu."""
        guid = self._lobby.guid_of(session)
        if guid is None:
            log.warning("[%s] ExpelPlayer fora do lobby; ignorado", session.peer)
            return []
        level = self._lobby.access_of(guid)
        req = CsExpelPlayerIn.unpack(payload)
        if not may_notify(level):
            log.warning("[%s] ExpelPlayer sem nível de GM (%d); ignorado", session.peer, level)
            return []
        if req.kind not in EXPEL_KINDS:
            log.warning(
                "[%s] ExpelPlayer com tipo %#x desconhecido; ignorado", session.peer, req.kind
            )
            return []
        target = self._lobby.guid_of_nick(req.nickname)
        victim = None if target is None else self._lobby.recipient_of(target)
        if target is None or victim is None:
            self._record_expel(session, req, ERR_TARGET_OFFLINE)
            return [CsExpelPlayerOut(ERR_TARGET_OFFLINE)]
        if not may_expel(level, self._lobby.access_of(target)):
            self._record_expel(session, req, ERR_NOT_ALLOWED, target=target)
            return [CsExpelPlayerOut(ERR_NOT_ALLOWED)]
        # A queda passa pelo `disconnect` do canal ao fim do laço: sai da sala e do lobby, e o 123
        # vai aos demais. Não mexemos no lobby aqui para não ter dois caminhos de saída.
        victim.close()
        self._record_expel(session, req, RESULT_EXPELLED, target=target)
        return [CsExpelPlayerOut(RESULT_EXPELLED)]

    def _record_expel(
        self, session: Session, req: CsExpelPlayerIn, result: int, *, target: int | None = None
    ) -> None:
        self._record(
            session,
            "gm_expel",
            kind=req.kind,
            target_nickname=req.nickname,
            target_guid=target,
            result=result,
        )

    def _record(self, session: Session, event: str, **fields: object) -> None:
        if self._audit is not None:
            self._audit.record(session, event, **fields)
