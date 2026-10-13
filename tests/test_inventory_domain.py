"""Regras do inventário sem IO: item, morat, escolha regular e kit inicial, com catálogo falso."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from landmass_emu.domain.inventory import (
    MAX_INVENTORY_INDEX,
    ApplyFlag,
    InventoryService,
    ItemUnit,
)
from landmass_emu.domain.regular import RegularChoice, RegularService
from landmass_emu.domain.starter_kit import STARTER_MORATS, StarterKit

AGORA = datetime(2026, 1, 1, tzinfo=UTC)
# Segundos Unix de 2026-01-01T00:00Z e de 2026-01-04T00:00Z (AGORA + 3 dias).
EPOCH_TRES_DIAS = 1767484800
ITEM = 1  # grupo 3 (fictício)
ITEM_EQUIP = 2  # grupo 2 (fictício)
MORAT = 101000001


class FakeCatalog:
    def __init__(self, itens: frozenset[int], morats: frozenset[int]) -> None:
        self._itens = itens
        self._morats = morats

    def is_inventory_item(self, catalog_id: int) -> bool:
        return catalog_id in self._itens

    def is_morat(self, catalog_id: int) -> bool:
        return catalog_id in self._morats


def _guids() -> Callable[[], str]:
    contador = iter(range(1, 1_000_000))
    return lambda: str(uuid.UUID(int=next(contador)))


def _servico() -> InventoryService:
    catalogo = FakeCatalog(frozenset({ITEM, ITEM_EQUIP}), frozenset(STARTER_MORATS))
    return InventoryService(catalogo, clock=lambda: AGORA, new_guid=_guids())


def test_item_de_morat_no_catalogo_levanta() -> None:
    with pytest.raises(ValueError, match="não é item"):
        _servico().new_item(7, MORAT, 3, [])


@pytest.mark.parametrize("dias", [0, -1])
def test_item_com_menos_de_um_dia_levanta(dias: int) -> None:
    with pytest.raises(ValueError, match="mínimo 1"):
        _servico().new_item(7, ITEM, dias, [])


def test_item_realtime_com_prazo_em_segundos_unix() -> None:
    item = _servico().new_item(7, ITEM, 3, [])
    assert item.account_id == 7
    assert item.catalog_id == ITEM
    assert item.apply_flag is ApplyFlag.REALTIME
    assert item.expires_at == AGORA + timedelta(days=3)
    assert item.wire_apply_value() == EPOCH_TRES_DIAS


def test_item_sem_prazo_grava_zero() -> None:
    sem_prazo = ItemUnit(
        account_id=7,
        inventory_index=1,
        catalog_id=ITEM,
        item_guid=str(uuid.UUID(int=1)),
        apply_flag=ApplyFlag.REALTIME,
        apply_value=None,
        expires_at=None,
    )
    assert sem_prazo.wire_apply_value() == 0


@pytest.mark.parametrize(("usados", "esperado"), [([], 1), ([1, 2, 4], 3), ([2, 3], 1)])
def test_indice_livre_comeca_em_1(usados: list[int], esperado: int) -> None:
    assert _servico().new_item(7, ITEM, 1, usados).inventory_index == esperado


def test_inventario_cheio_levanta() -> None:
    with pytest.raises(ValueError, match="sem índice livre"):
        _servico().new_item(7, ITEM, 1, range(1, MAX_INVENTORY_INDEX + 1))


def test_ultimo_indice_de_16_bits_ainda_serve() -> None:
    item = _servico().new_item(7, ITEM, 1, range(1, MAX_INVENTORY_INDEX))
    assert item.inventory_index == MAX_INVENTORY_INDEX


def test_morat_de_item_no_catalogo_levanta() -> None:
    with pytest.raises(ValueError, match="não é morat"):
        _servico().new_morat(7, ITEM, 0, [])


@pytest.mark.parametrize("gate", [-1, 8])
def test_morat_fora_dos_gates_levanta(gate: int) -> None:
    with pytest.raises(ValueError, match="gate"):
        _servico().new_morat(7, MORAT, gate, [])


def test_gate_ja_usado_levanta() -> None:
    with pytest.raises(ValueError, match="já tem um morat"):
        _servico().new_morat(7, MORAT, 2, [2])


def test_morat_usa_o_gate_como_indice_e_nao_expira() -> None:
    morat = _servico().new_morat(7, 103000001, 3, [0, 1])
    assert morat.inventory_index == 3
    assert morat.gate_index == 3
    assert morat.apply_flag is ApplyFlag.UNLIMIT
    assert morat.expires_at is None
    assert morat.wire_apply_value() == 0


@pytest.mark.parametrize("nest", [0, 4])
def test_nest_fora_de_1_a_3_levanta(nest: int) -> None:
    with pytest.raises(ValueError, match="nest"):
        RegularService().choose(nest, 1)


@pytest.mark.parametrize("classe", [0, 5])
def test_classe_fora_de_1_a_4_levanta(classe: int) -> None:
    with pytest.raises(ValueError, match="classe"):
        RegularService().choose(2, classe)


def test_escolha_valida_devolve_nest_e_classe() -> None:
    assert RegularService().choose(2, 3) == RegularChoice(nest=2, morat_class=3)
    assert RegularService().choose(1, 1) == RegularChoice(nest=1, morat_class=1)
    assert RegularService().choose(3, 4) == RegularChoice(nest=3, morat_class=4)


def test_kit_sem_gates_usados_planeja_os_quatro_gates() -> None:
    plano = StarterKit(_servico()).plan(7, [])
    assert [(m.gate_index, m.catalog_id) for m in plano] == [
        (0, 101000001),
        (1, 102000001),
        (2, 103000001),
        (3, 104000001),
    ]


def test_kit_pula_gate_ocupado_sem_deslocar_os_demais() -> None:
    plano = StarterKit(_servico()).plan(7, {1})
    assert [(m.gate_index, m.catalog_id) for m in plano] == [
        (0, 101000001),
        (2, 103000001),
        (3, 104000001),
    ]


def test_kit_so_planeja_sem_alterar_a_entrada() -> None:
    usados = [1]
    kit = StarterKit(_servico())
    primeiro = kit.plan(7, usados)
    segundo = kit.plan(7, usados)
    assert usados == [1]
    assert [m.gate_index for m in primeiro] == [m.gate_index for m in segundo] == [0, 2, 3]
