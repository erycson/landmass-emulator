"""Handlers de amigos, bloqueios e sussurro (F12) com repositórios em memória."""

from landmass_emu.domain.account import Account
from landmass_emu.domain.presence import MessagePresence
from landmass_emu.handlers.message.social import SocialHandlers
from landmass_emu.handlers.message.whisper import WhisperHandlers
from landmass_emu.net.server import reply_body
from landmass_emu.net.session import Session
from landmass_emu.ports.social import Contact, Relation
from landmass_emu.protocol.header import MESSAGE_NET_CODE
from landmass_emu.protocol.message import (
    MsAccountIdIn,
    MsBlackListOut,
    MsContactRecord,
    MsDelFriendOut,
    MsFriendListOut,
    MsNickIn,
    MsRefreshBlackOut,
    MsRefreshFriendOut,
    MsRelationIdsIn,
    MsRelationState,
    MsSendWhisperIn,
    MsWhisperErrorOut,
    MsWhisperOut,
)

ANA = Account(id=1, username="ana", nickname="Ana", token_hash="x" * 64)
BIA = Account(id=2, username="bia", nickname="Bia", token_hash="x" * 64)
CAI = Account(id=3, username="cai", nickname="Cai", token_hash="x" * 64)


class FakeAccounts:
    """Implementa o que `SocialHandlers` e `WhisperHandlers` usam de `AccountRepository`."""

    def __init__(self, *contas: Account) -> None:
        self._por_nick = {c.nickname: c for c in contas}

    async def find_by_nickname(self, nickname: str) -> Account | None:
        return self._por_nick.get(nickname)


class FakeSocial:
    """Implementa `ports.social.SocialRepository` em memória, na ordem de inserção do banco."""

    def __init__(self, nicks: dict[int, str], exp: dict[int, int]) -> None:
        self._nicks = nicks
        self._exp = exp
        self.edges: dict[tuple[Relation, int, int], None] = {}

    async def contacts(self, relation: Relation, account_id: int) -> tuple[Contact, ...]:
        return tuple(
            Contact(t, self._nicks[t], self._exp[t])
            for (r, owner, t) in self.edges
            if r == relation and owner == account_id
        )

    async def has(self, relation: Relation, account_id: int, target_id: int) -> bool:
        return (relation, account_id, target_id) in self.edges

    async def add(self, relation: Relation, account_id: int, target_id: int) -> bool:
        key = (relation, account_id, target_id)
        if key in self.edges:
            return False
        self.edges[key] = None
        return True

    async def remove(self, relation: Relation, account_id: int, target_id: int) -> bool:
        key = (relation, account_id, target_id)
        if key not in self.edges:
            return False
        del self.edges[key]
        return True


class FakeRecipient:
    def __init__(self) -> None:
        self.bodies: list[bytes] = []

    def send(self, body: bytes) -> None:
        self.bodies.append(body)


def _logada(conta: Account) -> Session:
    session = Session(peer="teste")
    session.account = conta
    return session


def _mundo(
    presence: MessagePresence | None = None,
) -> tuple[SocialHandlers, WhisperHandlers, FakeSocial, MessagePresence]:
    accounts = FakeAccounts(ANA, BIA, CAI)
    social = FakeSocial({1: "Ana", 2: "Bia", 3: "Cai"}, {1: 0, 2: 2800, 3: 0})
    registro = presence if presence is not None else MessagePresence()
    return (
        SocialHandlers(accounts, social, registro),
        WhisperHandlers(accounts, social, registro),
        social,
        registro,
    )


async def test_lista_sai_amigos_em_183_e_bloqueados_em_188() -> None:
    social_h, _, social, _ = _mundo()
    social.edges[(Relation.FRIEND, 1, 2)] = None
    social.edges[(Relation.BLOCK, 1, 3)] = None
    replies = await social_h.get_friend_list(_logada(ANA), b"")
    assert replies == [
        MsFriendListOut(MsContactRecord(2, "Bia", total_exp=2800)),
        MsBlackListOut(MsContactRecord(3, "Cai")),
    ]


async def test_lista_vazia_nao_responde_nada() -> None:
    social_h, _, _, _ = _mundo()
    assert await social_h.get_friend_list(_logada(ANA), b"") == []


async def test_adicionar_amigo_responde_183_com_o_estado_de_presenca() -> None:
    social_h, _, social, presence = _mundo()
    presence.bind(BIA.id, FakeRecipient())
    replies = await social_h.add_friend(_logada(ANA), MsNickIn("Bia").pack())
    assert replies == [MsFriendListOut(MsContactRecord(2, "Bia", 2800, online=True))]
    assert (Relation.FRIEND, 1, 2) in social.edges


async def test_adicionar_recusa_a_propria_conta_e_nick_desconhecido() -> None:
    social_h, _, social, _ = _mundo()
    for nick in ("Ana", "Ninguem"):
        replies = await social_h.add_friend(_logada(ANA), MsNickIn(nick).pack())
        assert replies == [MsFriendListOut(MsContactRecord(0, nick, result=-11))]
    assert social.edges == {}


async def test_adicionar_duplicado_reenvia_o_mesmo_registro() -> None:
    social_h, _, social, _ = _mundo()
    primeiro = await social_h.add_friend(_logada(ANA), MsNickIn("Bia").pack())
    segundo = await social_h.add_friend(_logada(ANA), MsNickIn("Bia").pack())
    assert primeiro == segundo
    assert len(social.edges) == 1


async def test_remover_responde_id_ecoado_e_resultado() -> None:
    social_h, _, social, _ = _mundo()
    social.edges[(Relation.FRIEND, 1, 2)] = None
    dono = _logada(ANA)
    assert await social_h.del_friend(dono, MsAccountIdIn(2).pack()) == [MsDelFriendOut(2, 0)]
    assert await social_h.del_friend(dono, MsAccountIdIn(2).pack()) == [MsDelFriendOut(2, -11)]


async def test_bloqueio_nao_aparece_na_lista_de_amigos() -> None:
    social_h, _, _, _ = _mundo()
    replies = await social_h.add_block(_logada(ANA), MsNickIn("Cai").pack())
    assert replies == [MsBlackListOut(MsContactRecord(3, "Cai"))]
    assert await social_h.get_friend_list(_logada(ANA), b"") == [
        MsBlackListOut(MsContactRecord(3, "Cai"))
    ]


async def test_atualizacao_so_devolve_contas_da_propria_lista() -> None:
    social_h, _, social, _ = _mundo()
    social.edges[(Relation.FRIEND, 1, 2)] = None
    social.edges[(Relation.BLOCK, 1, 3)] = None
    dono = _logada(ANA)
    ids = MsRelationIdsIn((2, 3)).pack()
    assert await social_h.refresh_friends(dono, ids) == [
        MsRefreshFriendOut((MsRelationState(2, 2800, online=False),))
    ]
    assert await social_h.refresh_blocks(dono, ids) == [
        MsRefreshBlackOut((MsRelationState(3, 0, online=False),))
    ]


async def test_pedidos_sem_login_nao_respondem() -> None:
    social_h, whisper, _, _ = _mundo()
    anonima = Session(peer="teste")
    assert await social_h.get_friend_list(anonima, b"") == []
    assert await social_h.add_friend(anonima, MsNickIn("Bia").pack()) == []
    assert await whisper.send_whisper(anonima, MsSendWhisperIn("Bia", b"oi").pack()) == []


async def test_sussurro_chega_ao_destinatario_conectado() -> None:
    _, whisper, _, presence = _mundo()
    destinatario = FakeRecipient()
    presence.bind(BIA.id, destinatario)
    replies = await whisper.send_whisper(_logada(ANA), MsSendWhisperIn("Bia", b"oi").pack())
    assert replies == []
    assert destinatario.bodies == [reply_body(MsWhisperOut("Ana", b"oi"), MESSAGE_NET_CODE)]


async def test_sussurro_para_quem_esta_fora_do_message_volta_offline() -> None:
    _, whisper, _, _ = _mundo()
    replies = await whisper.send_whisper(_logada(ANA), MsSendWhisperIn("Bia", b"oi").pack())
    assert replies == [MsWhisperErrorOut(-19, "Bia", b"oi")]


async def test_sussurro_de_quem_foi_bloqueado_volta_offline() -> None:
    _, whisper, social, presence = _mundo()
    destinatario = FakeRecipient()
    presence.bind(BIA.id, destinatario)
    social.edges[(Relation.BLOCK, 2, 1)] = None  # Bia bloqueou Ana
    replies = await whisper.send_whisper(_logada(ANA), MsSendWhisperIn("Bia", b"oi").pack())
    assert replies == [MsWhisperErrorOut(-19, "Bia", b"oi")]
    assert destinatario.bodies == []


async def test_sussurro_para_nick_desconhecido_volta_valor_invalido() -> None:
    _, whisper, _, _ = _mundo()
    replies = await whisper.send_whisper(_logada(ANA), MsSendWhisperIn("Ninguem", b"oi").pack())
    assert replies == [MsWhisperErrorOut(-11, "Ninguem", b"oi")]
