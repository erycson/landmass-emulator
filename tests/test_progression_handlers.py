import struct
from dataclasses import replace

import pytest

from landmass_emu.domain.account import Account
from landmass_emu.domain.progression import Grant, Progression, ProgressionService
from landmass_emu.handlers.channel.progression import ProgressionHandlers
from landmass_emu.net.session import Session
from landmass_emu.protocol.progression import (
    CsChargeCashOut,
    CsChargePointOut,
    CsTutorialClearOut,
    PlayerRecord,
)


class FakeProgression:
    """Implementa `ports.progression.ProgressionRepository` em memória."""

    def __init__(self, progression: Progression | None = None) -> None:
        self.progression = progression if progression is not None else Progression()
        self.marks: list[int] = []

    async def get(self, account_id: int) -> Progression:
        return self.progression

    async def mark_tutorial(self, account_id: int, bit: int) -> Progression:
        self.marks.append(bit)
        self.progression = replace(
            self.progression, tutorial_clear=self.progression.tutorial_clear | bit
        )
        return self.progression

    async def grant(self, account_id: int, grant: Grant) -> None:
        raise AssertionError("o canal não concede progressão")


def _logado() -> Session:
    session = Session(peer="teste")
    session.account = Account(id=7, username="ana", nickname="Ana", token_hash="x" * 64)
    return session


def _handlers(repo: FakeProgression) -> ProgressionHandlers:
    return ProgressionHandlers(repo, ProgressionService())


async def test_tutorial_marca_o_bit_e_responde_601_com_o_ld_atual() -> None:
    repo = FakeProgression(Progression(ld=1000))
    replies = await _handlers(repo).tutorial_clear(_logado(), b"\x01")
    assert replies == [CsTutorialClearOut(tutorial_clear=2, point=1000)]
    assert repo.marks == [2]


async def test_tutorial_acumula_os_passos_e_repetido_nao_muda() -> None:
    repo = FakeProgression(Progression(tutorial_clear=1, ld=50))  # passo 0 já feito
    handlers = _handlers(repo)
    # Payload 1 é o passo 1 (tiro, bit 0x2): 0x1 | 0x2 = 3.
    assert await handlers.tutorial_clear(_logado(), b"\x01") == [
        CsTutorialClearOut(tutorial_clear=3, point=50)
    ]
    assert await handlers.tutorial_clear(_logado(), b"\x01") == [
        CsTutorialClearOut(tutorial_clear=3, point=50)
    ]  # repetido: idempotente
    assert repo.progression.tutorial_clear == 3


async def test_tutorial_passo_fora_da_faixa_levanta_e_nao_grava() -> None:
    repo = FakeProgression()
    with pytest.raises(ValueError):
        await _handlers(repo).tutorial_clear(_logado(), b"\x03")
    assert repo.marks == []


async def test_tutorial_payload_vazio_levanta_struct_error() -> None:
    with pytest.raises(struct.error):
        await _handlers(FakeProgression()).tutorial_clear(_logado(), b"")


async def test_tutorial_sem_login_nao_responde_nem_grava() -> None:
    repo = FakeProgression()
    assert await _handlers(repo).tutorial_clear(Session(peer="teste"), b"\x00") == []
    assert repo.marks == []


async def test_login_devolve_registro_e_pushes_de_saldo() -> None:
    repo = FakeProgression(Progression(total_exp=2800, ld=1000, cash=500, tutorial_clear=5))
    record, pushes = await _handlers(repo).login_state(7)
    assert record == PlayerRecord(tutorial_clear=5, total_exp=2800, cash=500, point=1000)
    assert pushes == (CsChargeCashOut(cash=500), CsChargePointOut(point=1000))


async def test_total_exp_e_a_exp_gravada() -> None:
    repo = FakeProgression(Progression(total_exp=2800))
    assert await _handlers(repo).total_exp(7) == 2800
