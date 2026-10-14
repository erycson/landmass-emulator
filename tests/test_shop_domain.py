"""Regras da loja (preço, prazo, requisito) e `ShopService`, com fakes de catálogo e saldo."""

import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from landmass_emu.domain.currency import Currency
from landmass_emu.domain.inventory import ApplyFlag, InventoryService, ItemUnit, MoratUnit
from landmass_emu.domain.progression import Level, Progression
from landmass_emu.domain.shop import (
    BuyResult,
    Quote,
    Requirements,
    SaleInfo,
    ShopRefusal,
    ShopService,
    quote,
)
from landmass_emu.ports.inventory import InventoryConflict

AGORA = datetime(2026, 10, 13, tzinfo=UTC)
GUID = "b" * 36
ITEM = 1000100
MORAT = 101000001


def _item(
    *,
    ld: tuple[int, int, int, int] = (100, 300, 500, 900),
    cash: tuple[int, int, int, int] = (10, 30, 50, 90),
    req: Requirements | None = None,
) -> SaleInfo:
    return SaleInfo(is_morat=False, ld=ld, cash=cash, requirements=req or Requirements())


def _morat(
    *,
    ld: tuple[int, int, int, int] = (5000, 0, 0, 0),
    cash: tuple[int, int, int, int] = (2000, 0, 0, 0),
) -> SaleInfo:
    return SaleInfo(is_morat=True, ld=ld, cash=cash, requirements=Requirements())


def _morat_no_gate(gate: int) -> MoratUnit:
    return MoratUnit(
        account_id=1,
        inventory_index=gate,
        catalog_id=MORAT,
        item_guid=f"{gate:036d}",
        gate_index=gate,
        apply_flag=ApplyFlag.UNLIMIT,
        apply_value=None,
        expires_at=None,
    )


class FakeCatalog:
    def __init__(self, sales: dict[int, SaleInfo]) -> None:
        self._sales = sales

    def is_inventory_item(self, catalog_id: int) -> bool:
        venda = self._sales.get(catalog_id)
        return venda is not None and not venda.is_morat

    def is_morat(self, catalog_id: int) -> bool:
        venda = self._sales.get(catalog_id)
        return venda is not None and venda.is_morat

    def sale(self, catalog_id: int) -> SaleInfo | None:
        return self._sales.get(catalog_id)


class CatalogoAusente:
    """O wdb não abre: cada consulta levanta ValueError, como o LazyItemCatalog."""

    def is_inventory_item(self, catalog_id: int) -> bool:
        raise ValueError("catálogo do cliente não encontrado")

    def is_morat(self, catalog_id: int) -> bool:
        raise ValueError("catálogo do cliente não encontrado")

    def sale(self, catalog_id: int) -> SaleInfo | None:
        raise ValueError("catálogo do cliente não encontrado")


class FakeLevels:
    def level_list(self) -> tuple[Level, ...]:
        return (Level(1, 0, "Recruta"), Level(2, 100, "Soldado"))


class FakeAccounts:
    def __init__(self, nest: int = 0) -> None:
        self._nest = nest

    async def regular_nest(self, account_id: int) -> int:
        return self._nest


class FakeProgression:
    def __init__(self, *, ld: int = 0, cash: int = 0, total_exp: int = 0) -> None:
        self.progress = Progression(total_exp=total_exp, ld=ld, cash=cash)

    async def get(self, account_id: int) -> Progression:
        return self.progress


class FakeInventory:
    def __init__(self, morats: list[MoratUnit] | None = None) -> None:
        self._morats = morats or []

    async def items(self, account_id: int) -> list[ItemUnit]:
        return []

    async def morats(self, account_id: int) -> list[MoratUnit]:
        return list(self._morats)


class FakePurchases:
    """Débito condicional em memória, com a regra do banco: grava só se o saldo cobre."""

    def __init__(
        self, progresso: FakeProgression, *, conflito: bool = False, muda: bool = False
    ) -> None:
        self._progresso = progresso
        self._conflito = conflito
        # `muda` simula saldo que caiu entre a leitura e o débito condicional.
        self._muda = muda
        self.gravadas: list[ItemUnit | MoratUnit] = []

    async def purchase(
        self, account_id: int, currency: Currency, price: int, unit: ItemUnit | MoratUnit
    ) -> bool:
        if self._conflito:
            raise InventoryConflict("índice 1 já ocupado na conta")
        if self._muda:
            return False
        atual = self._progresso.progress
        if currency is Currency.LD:
            if atual.ld < price:
                return False
            self._progresso.progress = replace(atual, ld=atual.ld - price)
        else:
            if atual.cash < price:
                return False
            self._progresso.progress = replace(atual, cash=atual.cash - price)
        self.gravadas.append(unit)
        return True


def _servico(
    sales: dict[int, SaleInfo],
    *,
    ld: int = 0,
    cash: int = 0,
    exp: int = 0,
    nest: int = 0,
    morats: list[MoratUnit] | None = None,
    conflito: bool = False,
    muda: bool = False,
) -> tuple[ShopService, FakeProgression, FakePurchases]:
    progresso = FakeProgression(ld=ld, cash=cash, total_exp=exp)
    compras = FakePurchases(progresso, conflito=conflito, muda=muda)
    catalogo = FakeCatalog(sales)
    servico = ShopService(
        catalog=catalogo,
        levels=FakeLevels(),
        inventory=InventoryService(catalogo, clock=lambda: AGORA, new_guid=lambda: GUID),
        repository=FakeInventory(morats),
        accounts=FakeAccounts(nest),
        progression=progresso,
        purchases=compras,
    )
    return servico, progresso, compras


def test_item_ld_e_cash_seguem_a_opcao_de_prazo() -> None:
    assert quote(_item(), Currency.LD, 2) == Quote(500, 14)
    assert quote(_item(), Currency.CASH, 3) == Quote(90, 30)


def test_opcao_fora_de_0_a_3_nao_tem_preco() -> None:
    assert quote(_item(), Currency.LD, 4) == Quote(0, 0)
    assert quote(_item(), Currency.CASH, -1) == Quote(0, 0)


def test_morat_ld_e_cinco_vezes_o_buy_point_zero_e_ignora_a_opcao() -> None:
    assert quote(_morat(), Currency.LD, 1) == Quote(25000, 0)
    assert quote(_morat(), Currency.LD, 3) == Quote(25000, 0)


def test_morat_cash_usa_o_buy_cash_zero_sem_fator() -> None:
    assert quote(_morat(), Currency.CASH, 1) == Quote(2000, 0)


def test_requisito_de_patente_e_nest() -> None:
    assert Requirements().unmet(level=1, nest=0) is None
    assert Requirements(level=2).unmet(level=1, nest=0) is not None
    assert Requirements(level=2).unmet(level=2, nest=0) is None
    assert Requirements(nest=3).unmet(level=1, nest=2) is not None
    assert Requirements(nest=3).unmet(level=1, nest=3) is None


def test_requisito_sem_fonte_no_servidor_e_recusado_pelo_unmet() -> None:
    assert Requirements(clan=1).unmet(level=9, nest=9) is not None
    assert Requirements(rank=1).unmet(level=9, nest=9) is not None


async def test_item_ld_debita_e_grava_com_validade_do_prazo() -> None:
    servico, progresso, compras = _servico({ITEM: _item()}, ld=1000)
    compra = await servico.buy(1, ITEM, Currency.LD, 1)
    assert isinstance(compra.unit, ItemUnit)
    assert compra.unit.expires_at == AGORA + timedelta(days=7)
    assert compra.unit.inventory_index == 1
    assert (compra.ld, compra.cash) == (700, 0)
    assert progresso.progress.ld == 700
    assert compras.gravadas == [compra.unit]


async def test_item_cash_usa_a_coluna_cash_e_o_prazo_da_opcao() -> None:
    servico, progresso, _ = _servico({ITEM: _item()}, cash=100)
    compra = await servico.buy(1, ITEM, Currency.CASH, 3)
    assert compra.unit.expires_at == AGORA + timedelta(days=30)
    assert progresso.progress.cash == 10


async def test_morat_ld_debita_cinco_vezes_e_pega_o_gate_zero() -> None:
    servico, progresso, _ = _servico({MORAT: _morat()}, ld=30000)
    compra = await servico.buy(1, MORAT, Currency.LD, 1)
    assert isinstance(compra.unit, MoratUnit)
    assert compra.unit.gate_index == 0
    assert compra.unit.expires_at is None
    assert progresso.progress.ld == 5000


async def test_morat_pega_o_menor_gate_livre() -> None:
    servico, _, _ = _servico(
        {MORAT: _morat()}, cash=2000, morats=[_morat_no_gate(0), _morat_no_gate(1)]
    )
    compra = await servico.buy(1, MORAT, Currency.CASH, 0)
    assert compra.unit.gate_index == 2


async def test_morat_sem_gate_livre_recusa_sem_debitar() -> None:
    cheios = [_morat_no_gate(g) for g in range(8)]
    servico, progresso, compras = _servico({MORAT: _morat()}, cash=9999, morats=cheios)
    with pytest.raises(ShopRefusal) as recusa:
        await servico.buy(1, MORAT, Currency.CASH, 0)
    assert recusa.value.result is BuyResult.NO_SPACE
    assert recusa.value.morat is True
    assert progresso.progress.cash == 9999
    assert compras.gravadas == []


async def test_item_fora_do_catalogo_recusa_em_silencio() -> None:
    servico, _, compras = _servico({}, ld=1000)
    with pytest.raises(ShopRefusal) as recusa:
        await servico.buy(1, ITEM, Currency.LD, 1)
    assert recusa.value.result is BuyResult.SILENT
    assert recusa.value.morat is False
    assert compras.gravadas == []


async def test_item_nao_vendido_na_moeda_ou_opcao_invalida_recusa() -> None:
    servico, _, compras = _servico(
        {ITEM: _item(ld=(100, 0, 0, 0), cash=(0, 0, 0, 0))}, ld=1000, cash=1000
    )
    for moeda, opcao in ((Currency.CASH, 0), (Currency.LD, 2), (Currency.LD, 4)):
        with pytest.raises(ShopRefusal) as recusa:
            await servico.buy(1, ITEM, moeda, opcao)
        assert recusa.value.result is BuyResult.SILENT
    assert compras.gravadas == []


async def test_saldo_ld_insuficiente_recusa_com_codigo_de_ld() -> None:
    servico, progresso, compras = _servico({ITEM: _item()}, ld=299)
    with pytest.raises(ShopRefusal) as recusa:
        await servico.buy(1, ITEM, Currency.LD, 1)
    assert recusa.value.result is BuyResult.LD_SHORTAGE
    assert progresso.progress.ld == 299
    assert compras.gravadas == []


async def test_saldo_cash_insuficiente_de_morat_recusa_com_codigo_de_cash() -> None:
    servico, _, _ = _servico({MORAT: _morat()}, cash=1999)
    with pytest.raises(ShopRefusal) as recusa:
        await servico.buy(1, MORAT, Currency.CASH, 0)
    assert recusa.value.result is BuyResult.CASH_SHORTAGE
    assert recusa.value.morat is True


async def test_patente_minima_recusa_e_passa_com_a_exp_necessaria() -> None:
    sale = {ITEM: _item(req=Requirements(level=2))}
    servico, progresso, compras = _servico(sale, ld=1000, exp=99)
    with pytest.raises(ShopRefusal) as recusa:
        await servico.buy(1, ITEM, Currency.LD, 1)
    assert recusa.value.result is BuyResult.SILENT
    assert compras.gravadas == []
    assert progresso.progress.ld == 1000

    servico, _, _ = _servico(sale, ld=1000, exp=100)
    assert (await servico.buy(1, ITEM, Currency.LD, 1)).unit is not None


async def test_nest_diferente_do_requisito_recusa_sem_debitar() -> None:
    servico, _, compras = _servico({ITEM: _item(req=Requirements(nest=3))}, ld=1000, nest=2)
    with pytest.raises(ShopRefusal) as recusa:
        await servico.buy(1, ITEM, Currency.LD, 1)
    assert recusa.value.result is BuyResult.SILENT
    assert compras.gravadas == []


async def test_requisito_sem_fonte_no_servidor_recusa() -> None:
    servico, _, compras = _servico({ITEM: _item(req=Requirements(clan=1))}, ld=1000)
    with pytest.raises(ShopRefusal):
        await servico.buy(1, ITEM, Currency.LD, 1)
    assert compras.gravadas == []


async def test_saldo_que_cai_antes_do_debito_recusa_sem_gravar() -> None:
    servico, _, compras = _servico({ITEM: _item()}, ld=1000, muda=True)
    with pytest.raises(ShopRefusal) as recusa:
        await servico.buy(1, ITEM, Currency.LD, 1)
    assert recusa.value.result is BuyResult.LD_SHORTAGE
    assert compras.gravadas == []


async def test_conflito_de_indice_vira_recusa_silenciosa_sem_debito() -> None:
    servico, progresso, _ = _servico({ITEM: _item()}, ld=1000, conflito=True)
    with pytest.raises(ShopRefusal) as recusa:
        await servico.buy(1, ITEM, Currency.LD, 1)
    assert recusa.value.result is BuyResult.SILENT
    assert progresso.progress.ld == 1000


async def test_catalogo_ausente_recusa_e_registra_erro(caplog: pytest.LogCaptureFixture) -> None:
    catalogo = CatalogoAusente()
    progresso = FakeProgression(ld=1000)
    servico = ShopService(
        catalog=catalogo,
        levels=FakeLevels(),
        inventory=InventoryService(catalogo),
        repository=FakeInventory(),
        accounts=FakeAccounts(),
        progression=progresso,
        purchases=FakePurchases(progresso),
    )
    with caplog.at_level(logging.ERROR), pytest.raises(ShopRefusal) as recusa:
        await servico.buy(1, ITEM, Currency.LD, 1)
    assert recusa.value.result is BuyResult.SILENT
    assert "catálogo do cliente não encontrado" in caplog.text
