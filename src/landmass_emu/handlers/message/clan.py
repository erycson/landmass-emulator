"""Clã no Message Server (F13): 171 (GetClanInfo), 174 (GetClanMember), 177 (chat de clã) e 194
(RefreshClanList). Criar, entrar, sair, renomear e marcar ficam na CLI (D55), pois o cliente não
tem pedido para isso.

173 e 176 existem no cliente, mas nenhum pedido os dispara, então não são emitidos (D55). Chat de
clã vai aos membros online, inclusive a quem enviou, como o chat geral (D58). Quem não tem clã
não recebe resposta (log).
"""

import logging
from collections.abc import Sequence

from landmass_emu.domain.presence import MessagePresence
from landmass_emu.net.server import Reply, reply_body
from landmass_emu.net.session import Session
from landmass_emu.ports.clans import Clan, ClanRepository
from landmass_emu.protocol.header import MESSAGE_NET_CODE
from landmass_emu.protocol.message import (
    MsClanChatIn,
    MsClanChatOut,
    MsClanInfoOut,
    MsClanMemberOut,
    MsClanRecord,
    MsRefreshClanOut,
    MsRelationIdsIn,
)

log = logging.getLogger(__name__)

_SHORT_MIN, _SHORT_MAX = -0x8000, 0x7FFF


class ClanHandlers:
    def __init__(self, clans: ClanRepository, presence: MessagePresence) -> None:
        self._clans = clans
        self._presence = presence

    async def get_clan_info(self, session: Session, payload: bytes) -> Sequence[Reply]:
        clan = await self._own_clan(session, "GetClanInfo")
        if clan is None:
            return []
        return [MsClanInfoOut(clan.id, clan.name, clan.master_nickname, clan.mark)]

    async def get_clan_member(self, session: Session, payload: bytes) -> Sequence[Reply]:
        clan = await self._own_clan(session, "GetClanMember")
        if clan is None:
            return []
        replies: list[Reply] = []
        for member in await self._clans.members(clan.id):
            # shortcut: a chave de 175 é i16 no cliente; contas acima de 32767 não aparecem.
            if not _SHORT_MIN <= member.account_id <= _SHORT_MAX:
                log.warning("membro %d fora do i16 de 175; omitido", member.account_id)
                continue
            online = self._presence.is_online(member.account_id)
            replies.append(
                MsClanMemberOut(member.account_id, member.nickname, member.total_exp, online)
            )
        return replies

    async def send_clan_message(self, session: Session, payload: bytes) -> Sequence[Reply]:
        owner = session.account
        clan = await self._own_clan(session, "SendClanMessage")
        if owner is None or clan is None:
            return []
        req = MsClanChatIn.unpack(payload)
        body = reply_body(MsClanChatOut(owner.nickname, req.text), MESSAGE_NET_CODE)
        for member in await self._clans.members(clan.id):
            recipient = self._presence.recipient_of(member.account_id)
            if recipient is not None:
                recipient.send(body)
        return []

    async def refresh_clan(self, session: Session, payload: bytes) -> Sequence[Reply]:
        clan = await self._own_clan(session, "RefreshClanList")
        if clan is None:
            return []
        # Só responde por ids do próprio clã: sem filtro, vazaria exp de qualquer conta.
        wanted = MsRelationIdsIn.unpack(payload).account_ids
        records = tuple(
            MsClanRecord(
                m.account_id,
                m.total_exp,
                online=self._presence.is_online(m.account_id),
            )
            for m in await self._clans.members(clan.id)
            if m.account_id in wanted
        )
        return [MsRefreshClanOut(clan.id, clan.mark, records)]

    async def _own_clan(self, session: Session, request: str) -> Clan | None:
        owner = session.account
        if owner is None:
            log.warning("[%s] %s antes do login; ignorado", session.peer, request)
            return None
        clan = await self._clans.by_account(owner.id)
        if clan is None:
            log.info("[%s] %s sem clã; ignorado", session.peer, request)
        return clan
