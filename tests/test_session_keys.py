import re

from landmass_emu.domain.account import Account
from landmass_emu.domain.session_keys import SESSION_KEY_TTL, MemorySessionKeyRegistry

ANA = Account(id=1, username="ana", nickname="Ana", token_hash="x" * 64)
BIA = Account(id=2, username="bia", nickname="Bia", token_hash="y" * 64)


class Relogio:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_chave_tem_32_hex_minusculos_e_resolve_devolve_a_conta() -> None:
    reg = MemorySessionKeyRegistry(clock=Relogio())
    key = reg.issue(ANA)
    assert re.fullmatch(r"[0-9a-f]{32}", key)
    assert reg.resolve(key) == ANA


def test_nova_chave_da_conta_invalida_a_antiga() -> None:
    reg = MemorySessionKeyRegistry(clock=Relogio())
    antiga = reg.issue(ANA)
    nova = reg.issue(ANA)
    assert antiga != nova
    assert reg.resolve(antiga) is None
    assert reg.resolve(nova) == ANA


def test_emitir_para_outra_conta_nao_invalida_a_primeira() -> None:
    reg = MemorySessionKeyRegistry(clock=Relogio())
    chave_ana = reg.issue(ANA)
    chave_bia = reg.issue(BIA)
    assert reg.resolve(chave_ana) == ANA
    assert reg.resolve(chave_bia) == BIA


def test_chave_desconhecida_ou_vazia_nao_resolve() -> None:
    reg = MemorySessionKeyRegistry(clock=Relogio())
    reg.issue(ANA)
    assert reg.resolve("") is None
    assert reg.resolve("0" * 32) is None


def test_chave_nunca_usada_vale_antes_do_prazo() -> None:
    relogio = Relogio()
    reg = MemorySessionKeyRegistry(clock=relogio)
    key = reg.issue(ANA)
    relogio.t = SESSION_KEY_TTL - 1
    assert reg.resolve(key) == ANA


def test_chave_nunca_usada_expira_ao_completar_o_prazo() -> None:
    relogio = Relogio()
    reg = MemorySessionKeyRegistry(clock=relogio)
    key = reg.issue(ANA)
    relogio.t = SESSION_KEY_TTL
    assert reg.resolve(key) is None
    assert reg.resolve(key) is None


def test_chave_usada_nao_expira_ate_ser_reemitida() -> None:
    relogio = Relogio()
    reg = MemorySessionKeyRegistry(clock=relogio)
    key = reg.issue(ANA)
    relogio.t = 10.0
    assert reg.resolve(key) == ANA
    relogio.t = 10.0 * SESSION_KEY_TTL
    assert reg.resolve(key) == ANA
    nova = reg.issue(ANA)
    assert reg.resolve(key) is None
    assert reg.resolve(nova) == ANA
