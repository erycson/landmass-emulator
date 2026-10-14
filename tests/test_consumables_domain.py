"""Consumíveis e buffs (D131 a D136): regra de valor, efeito por id, recusas e buffs ativos. Sem IO:
o inventário e a gravação são falsos."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from landmass_emu.domain.buffs import ActiveBuffs, BuffService, active_buffs
from landmass_emu.domain.consumables import (
    ConsumableService,
    Effect,
    NotConsumable,
    check_value,
)
from landmass_emu.domain.equipment import ItemRefusal, UseResult
from landmass_emu.domain.inventory import ApplyFlag, ItemUnit

AGORA = datetime(2026, 10, 13, tzinfo=UTC)
QUEIMA = 308010001
ALISTAR = 308010003
TROCA = 308010004
HANGAR = 308010005  # fora deste serviço: segue o caminho F6
GACHA = 308010006  # fora deste serviço: segue o caminho F6
EXP = 308020001


def _item(
    indice: int, catalogo: int, *, prazo: datetime | None = None, sistema: int | None = None
) -> ItemUnit:
    return ItemUnit(
        account_id=1,
        inventory_index=indice,
        catalog_id=catalogo,
        item_guid=f"{indice:036d}",
        apply_flag=ApplyFlag.REALTIME,
        apply_value=None,
        expires_at=prazo or AGORA + timedelta(days=1),
        system_slot=sistema,
    )


@dataclass
class Inventario:
    itens: list[ItemUnit] = field(default_factory=list)

    async def items(self, account_id: int) -> list[ItemUnit]:
        return [i for i in self.itens if i.account_id == account_id]


@dataclass
class Gravacao:
    """Repositório falso: remove a unidade (como o SQL) e guarda o que foi pedido."""

    inventario: Inventario
    gravados: list[tuple[int, int, int, int, datetime]] = field(default_factory=list)

    async def consume(
        self,
        account_id: int,
        inventory_index: int,
        catalog_id: int,
        effect: int,
        value: int,
        at: datetime,
    ) -> bool:
        antes = len(self.inventario.itens)
        self.inventario.itens = [
            i
            for i in self.inventario.itens
            if not (i.inventory_index == inventory_index and i.catalog_id == catalog_id)
        ]
        if len(self.inventario.itens) == antes:
            return False
        self.gravados.append((account_id, effect, value, inventory_index, at))
        return True


def _servico(itens: list[ItemUnit]) -> tuple[ConsumableService, Gravacao]:
    inventario = Inventario(itens)
    gravacao = Gravacao(inventario)
    return ConsumableService(
        inventory=inventario, repository=gravacao, clock=lambda: AGORA
    ), gravacao


def test_valor_e_obrigatorio_em_alistar_e_na_faixa() -> None:
    check_value(Effect.NEST, 1)
    check_value(Effect.NEST, 3)
    for ruim in (0, 4):
        with pytest.raises(ItemRefusal) as recusa:
            check_value(Effect.NEST, ruim)
        assert recusa.value.result == UseResult.DENIED


def test_troca_aceita_classes_regulares_e_recusa_a_5() -> None:
    check_value(Effect.MORAT_CLASS, 4)
    with pytest.raises(ItemRefusal):
        check_value(Effect.MORAT_CLASS, 5)


def test_reset_recusa_valor() -> None:
    check_value(Effect.RESET_RECORD, 0)
    with pytest.raises(ItemRefusal):
        check_value(Effect.RESET_COMBAT, 1)


async def test_queima_consome_e_devolve_o_efeito_com_o_instante() -> None:
    servico, gravacao = _servico([_item(1, QUEIMA)])

    feito = await servico.use(1, 1, 0)

    assert (feito.effect, feito.value, feito.at) == (Effect.RESET_RECORD, 0, AGORA)
    assert gravacao.inventario.itens == []
    assert gravacao.gravados == [(1, int(Effect.RESET_RECORD), 0, 1, AGORA)]


async def test_consumo_vencido_recusa_sem_gravar() -> None:
    servico, gravacao = _servico([_item(1, ALISTAR, prazo=AGORA - timedelta(seconds=1))])

    with pytest.raises(ItemRefusal) as recusa:
        await servico.use(1, 1, 2)

    assert recusa.value.result == UseResult.DENIED
    assert gravacao.gravados == []


async def test_item_de_outro_dono_recusa() -> None:
    servico, _ = _servico([_item(1, QUEIMA)])
    with pytest.raises(ItemRefusal):
        await servico.use(2, 1, 0)


async def test_hangar_e_gacha_nao_sao_consumiveis_deste_servico() -> None:
    for catalogo in (HANGAR, GACHA, EXP):
        servico, _ = _servico([_item(1, catalogo)])
        with pytest.raises(NotConsumable):
            await servico.use(1, 1, 0)


async def test_nest_com_valor_fora_da_faixa_nao_consome() -> None:
    servico, gravacao = _servico([_item(1, TROCA)])

    with pytest.raises(ItemRefusal):
        await servico.use(1, 1, 9)

    assert len(gravacao.inventario.itens) == 1


def test_buff_ativo_exige_slot_de_sistema_e_prazo_nao_vencido() -> None:
    montado = _item(1, EXP, sistema=0)
    solto = _item(2, EXP)
    vencido = _item(3, EXP, sistema=1, prazo=AGORA - timedelta(days=1))
    assert active_buffs([montado, solto, vencido], AGORA) == ActiveBuffs(exp=True)


def test_ressurreicao_so_informa_e_consumivel_nao_conta() -> None:
    ressurreicao = _item(1, 308020003, sistema=0)
    queima = _item(2, QUEIMA, sistema=1)
    assert active_buffs([ressurreicao, queima], AGORA) == ActiveBuffs(respawn=True)


async def test_servico_de_buffs_le_os_itens_da_conta() -> None:
    inventario = Inventario([_item(1, EXP, sistema=0)])
    servico = BuffService(inventario, clock=lambda: AGORA)

    assert await servico.active_buffs(1) == ActiveBuffs(exp=True)
