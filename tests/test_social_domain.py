"""Regras de amizade e presença do Message (F12). Regras puras, sem banco nem socket."""

import pytest

from landmass_emu.domain.account import Account
from landmass_emu.domain.presence import MessagePresence
from landmass_emu.domain.social import SocialRules


class FakeRecipient:
    def __init__(self) -> None:
        self.bodies: list[bytes] = []

    def send(self, body: bytes) -> None:
        self.bodies.append(body)


def _conta(account_id: int, nickname: str) -> Account:
    return Account(id=account_id, username=nickname.lower(), nickname=nickname, token_hash="x" * 64)


def test_alvo_inexistente_e_a_propria_conta_sao_recusados() -> None:
    rules = SocialRules()
    ana = _conta(1, "Ana")
    with pytest.raises(ValueError):
        rules.target(ana, None)
    with pytest.raises(ValueError):
        rules.target(ana, ana)
    assert rules.target(ana, _conta(2, "Bia")).id == 2


def test_presenca_so_desvincula_a_conexao_que_se_vinculou() -> None:
    presence = MessagePresence()
    antiga, nova = FakeRecipient(), FakeRecipient()
    presence.bind(1, antiga)
    presence.bind(1, nova)  # outra conexão da mesma conta: a última vence
    presence.unbind(antiga)  # fechar a antiga não derruba a nova
    assert presence.recipient_of(1) is nova
    assert presence.is_online(1)
    presence.unbind(nova)
    assert not presence.is_online(1)
    assert presence.recipient_of(1) is None
