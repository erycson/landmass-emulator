"""Amigos e bloqueios no Message Server: 180, 181, 182, 186, 187, 190 e 192 (F12).

Relação dirigida. O id do amigo é o id da conta: o cliente o devolve no 182 e no 187. Pedido
recusado (nick inválido, conta inexistente, a própria conta) volta como registro com id 0 e
`result` -11 no mesmo opcode. O cliente não insere registro com resultado negativo.
"""

import logging
from collections.abc import Callable, Sequence

from landmass_emu.domain.account import check_nickname
from landmass_emu.domain.presence import MessagePresence
from landmass_emu.domain.social import SocialRules
from landmass_emu.net.server import Reply
from landmass_emu.net.session import Session
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.social import Contact, Relation, SocialRepository
from landmass_emu.protocol.message import (
    MsAccountIdIn,
    MsBlackListOut,
    MsContactRecord,
    MsDelBlackOut,
    MsDelFriendOut,
    MsFriendListOut,
    MsNickIn,
    MsRefreshBlackOut,
    MsRefreshFriendOut,
    MsRelationIdsIn,
    MsRelationState,
    MsResult,
)

log = logging.getLogger(__name__)


class SocialHandlers:
    def __init__(
        self,
        accounts: AccountRepository,
        social: SocialRepository,
        presence: MessagePresence,
    ) -> None:
        self._accounts = accounts
        self._social = social
        self._presence = presence
        self._rules = SocialRules()

    async def get_friend_list(self, session: Session, payload: bytes) -> Sequence[Reply]:
        owner = session.account
        if owner is None:
            log.warning("[%s] GetFriendList antes do login; ignorado", session.peer)
            return []
        # O cliente não pede a lista de bloqueio: os bloqueados saem junto, em 188.
        replies: list[Reply] = []
        for friend in await self._social.contacts(Relation.FRIEND, owner.id):
            replies.append(MsFriendListOut(self._record(friend)))
        for blocked in await self._social.contacts(Relation.BLOCK, owner.id):
            replies.append(MsBlackListOut(self._record(blocked)))
        return replies

    async def add_friend(self, session: Session, payload: bytes) -> Sequence[Reply]:
        return await self._add(session, payload, Relation.FRIEND, MsFriendListOut)

    async def add_block(self, session: Session, payload: bytes) -> Sequence[Reply]:
        return await self._add(session, payload, Relation.BLOCK, MsBlackListOut)

    async def del_friend(self, session: Session, payload: bytes) -> Sequence[Reply]:
        return await self._remove(session, payload, Relation.FRIEND, MsDelFriendOut)

    async def del_block(self, session: Session, payload: bytes) -> Sequence[Reply]:
        return await self._remove(session, payload, Relation.BLOCK, MsDelBlackOut)

    async def refresh_friends(self, session: Session, payload: bytes) -> Sequence[Reply]:
        return await self._refresh(session, payload, Relation.FRIEND, MsRefreshFriendOut)

    async def refresh_blocks(self, session: Session, payload: bytes) -> Sequence[Reply]:
        return await self._refresh(session, payload, Relation.BLOCK, MsRefreshBlackOut)

    async def _add(
        self,
        session: Session,
        payload: bytes,
        relation: Relation,
        reply: Callable[[MsContactRecord], Reply],
    ) -> Sequence[Reply]:
        owner = session.account
        if owner is None:
            log.warning("[%s] %s antes do login; ignorado", session.peer, relation)
            return []
        nickname = MsNickIn.unpack(payload).nickname
        refused = [reply(MsContactRecord(0, nickname, result=MsResult.INVALID_VALUE))]
        try:
            check_nickname(nickname)
            target = self._rules.target(owner, await self._accounts.find_by_nickname(nickname))
        except ValueError as e:
            log.info("[%s] %s de %r recusado: %s", session.peer, relation, nickname, e)
            return refused
        await self._social.add(relation, owner.id, target.id)  # se já existia, reenvia o registro
        contacts = await self._social.contacts(relation, owner.id)
        contact = next((c for c in contacts if c.account_id == target.id), None)
        return refused if contact is None else [reply(self._record(contact))]

    async def _remove(
        self,
        session: Session,
        payload: bytes,
        relation: Relation,
        reply: Callable[[int, int], Reply],
    ) -> Sequence[Reply]:
        owner = session.account
        if owner is None:
            log.warning("[%s] %s antes do login; ignorado", session.peer, relation)
            return []
        account_id = MsAccountIdIn.unpack(payload).account_id
        removed = await self._social.remove(relation, owner.id, account_id)
        if not removed:
            log.info("[%s] %s de %d: não existe", session.peer, relation, account_id)
        return [reply(account_id, 0 if removed else MsResult.INVALID_VALUE)]

    async def _refresh(
        self,
        session: Session,
        payload: bytes,
        relation: Relation,
        reply: Callable[[tuple[MsRelationState, ...]], Reply],
    ) -> Sequence[Reply]:
        owner = session.account
        if owner is None:
            log.warning("[%s] %s antes do login; ignorado", session.peer, relation)
            return []
        # Só responde por ids que são da própria conta: sem filtro, vazaria exp de qualquer conta.
        wanted = MsRelationIdsIn.unpack(payload).account_ids
        states = tuple(
            MsRelationState(c.account_id, c.total_exp, self._presence.is_online(c.account_id))
            for c in await self._social.contacts(relation, owner.id)
            if c.account_id in wanted
        )
        return [reply(states)]

    def _record(self, contact: Contact) -> MsContactRecord:
        return MsContactRecord(
            contact.account_id,
            contact.nickname,
            contact.total_exp,
            online=self._presence.is_online(contact.account_id),
        )
