"""Regras de equipar, desequipar, destruir e estender (F6, F7), com fakes em memória. Cada fake
repositório muda o `Estado` como a transação do banco mudaria as linhas."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

import pytest

from landmass_emu.domain.currency import Currency
from landmass_emu.domain.equipment import (
    EquipService,
    EquipSpec,
    ItemRefusal,
    MoratStats,
    UseResult,
    class_allows,
    group_and_class,
    is_system_item,
    pieces_of,
)
from landmass_emu.domain.inventory import ApplyFlag, ItemUnit, MoratUnit
from landmass_emu.domain.lifecycle import Destroyed, DestroyService, Extended, ExtendService
from landmass_emu.domain.progression import Level, Progression
from landmass_emu.domain.shop import BuyResult, Requirements, SaleInfo

AGORA = datetime(2026, 10, 13, tzinfo=UTC)
PECA = 201010001  # grupo 2, classe 1 (arma)
SISTEMA = 308000001  # grupo 3, classe 8
SKIN = 307000001  # grupo 3, classe 7
MORAT = 101000001  # grupo 1, o morat que as peças montam
SPEC_ARMA = EquipSpec(
    slot=0,
    class_mask=1111,
    power=0,
    strength=0,
    agility=0,
    precision=0,
    requirements=Requirements(),
)
STATS = MoratStats(morat_class=1, power=138, strength=185, agility=185, precision=200)


@dataclass
class Estado:
    items: list[ItemUnit] = field(default_factory=list)
    morats: list[MoratUnit] = field(default_factory=list)
    progress: Progression = field(default_factory=lambda: Progression(total_exp=0, ld=0, cash=0))


class Inventario:
    def __init__(self, estado: Estado) -> None:
        self._e = estado

    async def items(self, account_id: int) -> list[ItemUnit]:
        return list(self._e.items)

    async def morats(self, account_id: int) -> list[MoratUnit]:
        return list(self._e.morats)


class Montagem:
    """Repositório de montagem: cada método altera `Estado` como uma transação."""

    def __init__(self, estado: Estado) -> None:
        self._e = estado

    def _troca(self, indice: int, **campos: object) -> None:
        self._e.items = [
            replace(i, **campos) if i.inventory_index == indice else i for i in self._e.items
        ]

    async def mount(self, account_id: int, inventory_index: int, morat_id: int, slot: str) -> None:
        self._e.items = [
            replace(i, account_morat_id=None, slot_name=None)
            if (i.account_morat_id, i.slot_name) == (morat_id, slot)
            else i
            for i in self._e.items
        ]
        self._troca(inventory_index, account_morat_id=morat_id, slot_name=slot)

    async def unmount(self, account_id: int, inventory_index: int) -> None:
        self._troca(inventory_index, account_morat_id=None, slot_name=None)

    async def set_system_slot(self, account_id: int, inventory_index: int, slot: int) -> None:
        self._troca(inventory_index, system_slot=slot)

    async def destroy_item(self, account_id: int, inventory_index: int) -> None:
        self._e.items = [i for i in self._e.items if i.inventory_index != inventory_index]

    async def destroy_morat(self, account_id: int, morat_id: int) -> None:
        self._e.items = [
            replace(i, account_morat_id=None, slot_name=None)
            if i.account_morat_id == morat_id
            else i
            for i in self._e.items
        ]
        self._e.morats = [m for m in self._e.morats if m.id != morat_id]

    async def extend(
        self,
        account_id: int,
        currency: Currency,
        price: int,
        inventory_index: int,
        expires_at: datetime,
    ) -> bool:
        p = self._e.progress
        saldo = p.ld if currency is Currency.LD else p.cash
        if saldo < price:
            return False
        if currency is Currency.LD:
            self._e.progress = replace(p, ld=p.ld - price)
        else:
            self._e.progress = replace(p, cash=p.cash - price)
        self._troca(inventory_index, expires_at=expires_at)
        return True


class Saldos:
    def __init__(self, estado: Estado) -> None:
        self._e = estado

    async def get(self, account_id: int) -> Progression:
        return self._e.progress


class Contas:
    async def regular_nest(self, account_id: int) -> int:
        return 0


class Niveis:
    def level_list(self) -> tuple[Level, ...]:
        return (Level(1, 0, "Recruta"), Level(2, 100, "Soldado"))


class Catalogo:
    """Ids do catálogo em memória, com a interface de `EquipCatalog` e de `SaleCatalog`."""

    def __init__(
        self,
        specs: dict[int, EquipSpec] | None = None,
        stats: dict[int, MoratStats] | None = None,
        sales: dict[int, SaleInfo] | None = None,
    ) -> None:
        self._specs = specs or {}
        self._stats = stats or {}
        self._sales = sales or {}

    def is_morat(self, catalog_id: int) -> bool:
        return catalog_id in self._stats

    def is_inventory_item(self, catalog_id: int) -> bool:
        return catalog_id in self._specs or catalog_id in self._sales

    def equip_spec(self, catalog_id: int) -> EquipSpec | None:
        return self._specs.get(catalog_id)

    def morat_stats(self, catalog_id: int) -> MoratStats | None:
        return self._stats.get(catalog_id)

    def sale(self, catalog_id: int) -> SaleInfo | None:
        return self._sales.get(catalog_id)


def _catalogo(spec: EquipSpec = SPEC_ARMA) -> Catalogo:
    return Catalogo(
        specs={PECA: spec},
        stats={MORAT: STATS},
        sales={
            SISTEMA: SaleInfo(
                is_morat=False,
                ld=(0, 300, 0, 0),
                cash=(0, 30, 0, 0),
                requirements=Requirements(),
            )
        },
    )


def _item(
    indice: int,
    catalogo: int = PECA,
    *,
    prazo: datetime = AGORA + timedelta(days=5),
    morat: int | None = None,
    slot: str | None = None,
    sistema: int | None = None,
) -> ItemUnit:
    return ItemUnit(
        account_id=1,
        inventory_index=indice,
        catalog_id=catalogo,
        item_guid=f"{indice:036d}",
        apply_flag=ApplyFlag.REALTIME,
        apply_value=None,
        expires_at=prazo,
        account_morat_id=morat,
        slot_name=slot,
        system_slot=sistema,
    )


def _morat(gate: int, id_: int) -> MoratUnit:
    return MoratUnit(
        account_id=1,
        inventory_index=gate,
        catalog_id=MORAT,
        item_guid=f"m{gate:035d}",
        gate_index=gate,
        apply_flag=ApplyFlag.UNLIMIT,
        apply_value=None,
        expires_at=None,
        id=id_,
    )


def _equipar(estado: Estado, catalogo: Catalogo | None = None) -> EquipService:
    return EquipService(
        catalog=catalogo or _catalogo(),
        levels=Niveis(),
        inventory=Inventario(estado),
        equipment=Montagem(estado),
        accounts=Contas(),
        progression=Saldos(estado),
        clock=lambda: AGORA,
    )


def _destruir(estado: Estado) -> DestroyService:
    return DestroyService(inventory=Inventario(estado), equipment=Montagem(estado))


def _estender(estado: Estado) -> ExtendService:
    return ExtendService(
        catalog=_catalogo(),
        inventory=Inventario(estado),
        equipment=Montagem(estado),
        progression=Saldos(estado),
        clock=lambda: AGORA,
    )


# Regras puras.


def test_classe_segue_a_mascara_decimal() -> None:
    assert class_allows(0, 1)
    assert class_allows(1111, 10)  # 1111 // 10 = 111: o dígito 1 marca a classe 10
    assert not class_allows(10, 1)
    assert not class_allows(1111, 10000)
    assert not class_allows(1111, 0)


def test_grupo_e_classe_vem_do_id() -> None:
    assert group_and_class(PECA) == (2, 1)
    assert is_system_item(SISTEMA)
    assert not is_system_item(PECA)


def test_pieces_of_monta_19_valores_com_skins_em_zero() -> None:
    itens = [_item(1, morat=10, slot="head"), _item(2, morat=11, slot="head")]
    pecas = pieces_of(10, itens)
    assert len(pecas) == 19
    assert pecas[:8] == (-1,) * 8
    assert pecas[8] == 1  # `head` é o índice 8 de SLOT_NAMES; o item 2 é de outro morat
    assert pecas[9:16] == (-1,) * 7
    assert pecas[16:] == (0, 0, 0)


# Equipar e desequipar.


async def test_equipar_arma_monta_no_slot_do_catalogo() -> None:
    estado = Estado(items=[_item(1)], morats=[_morat(0, 10)])
    montado = await _equipar(estado).equip(1, 1, 0)
    assert (montado.slot, montado.gate, montado.system) == (0, 0, False)
    assert (estado.items[0].account_morat_id, estado.items[0].slot_name) == (10, "main_weapon")


async def test_classe_fora_da_mascara_recusa_sem_montar() -> None:
    estado = Estado(items=[_item(1)], morats=[_morat(0, 10)])
    catalogo = _catalogo(spec=replace(SPEC_ARMA, class_mask=10))  # só Sniper
    with pytest.raises(ItemRefusal) as recusa:
        await _equipar(estado, catalogo).equip(1, 1, 0)
    assert recusa.value.result == UseResult.REQUIREMENT
    assert estado.items[0].account_morat_id is None


async def test_energia_abaixo_do_minimo_recusa() -> None:
    estado = Estado(items=[_item(1)], morats=[_morat(0, 10)])
    catalogo = _catalogo(spec=replace(SPEC_ARMA, power=200))  # o morat tem 138
    with pytest.raises(ItemRefusal) as recusa:
        await _equipar(estado, catalogo).equip(1, 1, 0)
    assert recusa.value.result == UseResult.REQUIREMENT


async def test_gate_sem_morat_recusa_com_no_gate() -> None:
    estado = Estado(items=[_item(1)], morats=[_morat(0, 10)])
    with pytest.raises(ItemRefusal) as recusa:
        await _equipar(estado).equip(1, 1, 3)
    assert recusa.value.result == UseResult.NO_GATE


async def test_item_vencido_recusa() -> None:
    estado = Estado(items=[_item(1, prazo=AGORA - timedelta(days=1))], morats=[_morat(0, 10)])
    with pytest.raises(ItemRefusal) as recusa:
        await _equipar(estado).equip(1, 1, 0)
    assert recusa.value.result == UseResult.DENIED


async def test_peca_ja_montada_recusa() -> None:
    estado = Estado(items=[_item(1, morat=10, slot="main_weapon")], morats=[_morat(0, 10)])
    with pytest.raises(ItemRefusal) as recusa:
        await _equipar(estado).equip(1, 1, 0)
    assert recusa.value.result == UseResult.DENIED


async def test_skin_recusa_com_skin() -> None:
    estado = Estado(items=[_item(1, SKIN)], morats=[_morat(0, 10)])
    with pytest.raises(ItemRefusal) as recusa:
        await _equipar(estado).equip(1, 1, 0)
    assert recusa.value.result == UseResult.SKIN


async def test_sistema_usa_o_primeiro_slot_livre_e_ignora_o_gate() -> None:
    estado = Estado(items=[_item(1, SISTEMA, sistema=0), _item(2, SISTEMA)])
    montado = await _equipar(estado).equip(1, 2, 0)
    assert (montado.system, montado.slot, montado.gate) == (True, 1, None)
    assert estado.items[1].system_slot == 1


async def test_sistema_com_indice_acima_de_254_recusa() -> None:
    estado = Estado(items=[_item(300, SISTEMA)])
    with pytest.raises(ItemRefusal) as recusa:
        await _equipar(estado).equip(1, 300, 0)
    assert recusa.value.result == UseResult.DENIED


async def test_desequipar_peca_devolve_gate_e_slot() -> None:
    estado = Estado(items=[_item(1, morat=10, slot="main_weapon")], morats=[_morat(0, 10)])
    saiu = await _equipar(estado).unequip(1, 1, 0)
    assert (saiu.gate, saiu.slot) == (0, 0)
    assert estado.items[0].account_morat_id is None


async def test_desequipar_com_gate_errado_recusa() -> None:
    estado = Estado(items=[_item(1, morat=10, slot="main_weapon")], morats=[_morat(0, 10)])
    with pytest.raises(ItemRefusal) as recusa:
        await _equipar(estado).unequip(1, 1, 2)
    assert recusa.value.result == UseResult.NO_GATE


async def test_desequipar_item_de_sistema_recusa() -> None:
    estado = Estado(items=[_item(1, SISTEMA, sistema=0)])
    with pytest.raises(ItemRefusal) as recusa:
        await _equipar(estado).unequip(1, 1, 0)
    assert recusa.value.result == UseResult.DENIED


# Destruir.


async def test_ultimo_morat_da_conta_nao_sai() -> None:
    estado = Estado(morats=[_morat(0, 10)])
    with pytest.raises(ItemRefusal) as recusa:
        await _destruir(estado).destroy(1, MORAT, 0)
    assert recusa.value.result == UseResult.DENIED
    assert len(estado.morats) == 1


async def test_morat_sai_com_as_pecas_quando_ha_outro() -> None:
    estado = Estado(
        items=[_item(1, morat=10, slot="main_weapon")],
        morats=[_morat(0, 10), _morat(1, 11)],
    )
    feito = await _destruir(estado).destroy(1, MORAT, 0)
    assert feito == Destroyed(index=0, morat=True, gate=0, system_slot=None)
    assert estado.items[0].account_morat_id is None
    assert [m.id for m in estado.morats] == [11]


async def test_item_montado_informa_o_gate_de_onde_saiu() -> None:
    estado = Estado(
        items=[_item(1, morat=10, slot="main_weapon")],
        morats=[_morat(0, 10), _morat(1, 11)],
    )
    feito = await _destruir(estado).destroy(1, PECA, 1)
    assert feito == Destroyed(index=1, morat=False, gate=0, system_slot=None)
    assert estado.items == []


async def test_item_de_sistema_informa_o_slot() -> None:
    estado = Estado(items=[_item(1, SISTEMA, sistema=2)])
    feito = await _destruir(estado).destroy(1, SISTEMA, 1)
    assert feito == Destroyed(index=1, morat=False, gate=None, system_slot=2)


async def test_id_que_nao_bate_com_o_indice_recusa() -> None:
    estado = Estado(items=[_item(1)])
    with pytest.raises(ItemRefusal):
        await _destruir(estado).destroy(1, SISTEMA, 1)
    assert len(estado.items) == 1


# Estender.


async def test_estender_soma_a_partir_do_prazo_futuro() -> None:
    estado = Estado(
        items=[_item(1, SISTEMA, prazo=AGORA + timedelta(days=3))],
        progress=Progression(total_exp=0, ld=1000, cash=0),
    )
    feito = await _estender(estado).extend(1, SISTEMA, 1, Currency.LD, 1)
    assert feito == Extended(index=1, expires_at=AGORA + timedelta(days=10), cash=0, ld=700)
    assert estado.items[0].expires_at == AGORA + timedelta(days=10)


async def test_estender_parte_de_agora_se_ja_venceu() -> None:
    estado = Estado(
        items=[_item(1, SISTEMA, prazo=AGORA - timedelta(days=1))],
        progress=Progression(total_exp=0, ld=1000, cash=0),
    )
    feito = await _estender(estado).extend(1, SISTEMA, 1, Currency.LD, 1)
    assert feito.expires_at == AGORA + timedelta(days=7)


async def test_morat_nao_tem_prazo_e_recusa() -> None:
    estado = Estado(morats=[_morat(0, 10)], progress=Progression(total_exp=0, ld=9999, cash=0))
    with pytest.raises(ItemRefusal) as recusa:
        await _estender(estado).extend(1, MORAT, 0, Currency.LD, 1)
    assert recusa.value.result == UseResult.DENIED


async def test_opcao_sem_preco_recusa() -> None:
    estado = Estado(items=[_item(1, SISTEMA)], progress=Progression(total_exp=0, ld=1000, cash=0))
    with pytest.raises(ItemRefusal) as recusa:
        await _estender(estado).extend(1, SISTEMA, 0, Currency.LD, 0)  # ld[0] é 0
    assert recusa.value.result == UseResult.DENIED


async def test_saldo_insuficiente_nao_estende() -> None:
    prazo = AGORA + timedelta(days=3)
    estado = Estado(items=[_item(1, SISTEMA, prazo=prazo)], progress=Progression(0, 100, 0))
    with pytest.raises(ItemRefusal) as recusa:
        await _estender(estado).extend(1, SISTEMA, 1, Currency.LD, 1)
    assert recusa.value.result == BuyResult.LD_SHORTAGE
    assert estado.items[0].expires_at == prazo
