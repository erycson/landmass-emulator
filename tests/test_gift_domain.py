"""Regras do Depósito (F10), do Item Surpresa (F11) e dos gates do hangar (R-GATE-01/02), com
repositórios falsos: validação do presente, paginação, resgate, sorteio e contagem de gates."""

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from landmass_emu.domain.account import Account
from landmass_emu.domain.currency import Currency
from landmass_emu.domain.equipment import ItemRefusal, UseResult
from landmass_emu.domain.gacha import (
    BOX_ITEMS,
    EXP_BOOST,
    LD_MAX,
    LD_MIN,
    PAINTS,
    Drop,
    draw,
    prize_of,
)
from landmass_emu.domain.gift import Gift, GiftRefusal, GiftService
from landmass_emu.domain.inventory import (
    GATE_COUNT,
    ApplyFlag,
    InventoryService,
    ItemUnit,
    enabled_gates,
)
from landmass_emu.domain.shop import Requirements, SaleInfo
from landmass_emu.domain.use import (
    ADD_GATE_ITEM,
    GACHA_ITEM,
    GachaOpened,
    GateAdded,
    ItemUseService,
)

AGORA = datetime(2026, 10, 1, tzinfo=UTC)
ITEM = 201020001
GUID = "1" * 36


class FakeCatalog:
    """Vende `ITEM` (LD e Cash, 4 prazos) e não vende `OUTRO`; `GACHA` e `GATE` são itens comuns."""

    def __init__(self) -> None:
        self.vendas = {
            ITEM: SaleInfo(False, (100, 200, 300, 400), (10, 20, 30, 40), Requirements()),
            900: SaleInfo(True, (1000, 0, 0, 0), (50, 0, 0, 0), Requirements()),
            ADD_GATE_ITEM: SaleInfo(False, (0, 0, 0, 0), (15, 0, 0, 0), Requirements()),
        }

    def sale(self, catalog_id: int) -> SaleInfo | None:
        return self.vendas.get(catalog_id)

    def is_inventory_item(self, catalog_id: int) -> bool:
        return catalog_id != 900

    def is_morat(self, catalog_id: int) -> bool:
        return catalog_id == 900

    def name(self, catalog_id: int) -> str | None:
        return {GACHA_ITEM: "Item Surpresa", PAINTS[0]: "Pintura: Desert"}.get(catalog_id)


class FakeAccounts:
    def __init__(self, *contas: Account, gates: int = 4) -> None:
        self._contas = {c.nickname: c for c in contas}
        self.gates = gates

    async def find_by_nickname(self, nickname: str) -> Account | None:
        return self._contas.get(nickname)

    async def gate_count(self, account_id: int) -> int:
        return self.gates


class FakeProgression:
    def __init__(self, ld: int = 0, cash: int = 0) -> None:
        self.ld = ld
        self.cash = cash

    async def get(self, account_id: int) -> SimpleNamespace:
        return SimpleNamespace(ld=self.ld, cash=self.cash, total_exp=0)


@dataclass
class FakeGiftRepo:
    """Imita `SqlGiftRepository`: debita o remetente e grava o pendente; resgata uma vez só."""

    progresso: FakeProgression
    gifts: list[Gift] = field(default_factory=list)
    unidades: list[ItemUnit] = field(default_factory=list)
    _next: int = 1

    async def page(self, account_id: int, page: int, size: int) -> list[Gift]:
        pendentes = sorted(
            (g for g in self.gifts if g.receiver_account_id == account_id), key=lambda g: g.slot
        )
        return pendentes[page * size : page * size + size]

    async def pending(self, account_id: int, slot: int) -> Gift | None:
        return next(
            (g for g in self.gifts if g.receiver_account_id == account_id and g.slot == slot),
            None,
        )

    async def send(
        self,
        sender_id: int,
        receiver_id: int,
        currency: Currency,
        price: int,
        catalog_id: int,
        days: int,
    ) -> bool:
        if currency is Currency.LD:
            if self.progresso.ld < price:
                return False
            self.progresso.ld -= price
        else:
            if self.progresso.cash < price:
                return False
            self.progresso.cash -= price
        usados = {g.slot for g in self.gifts if g.receiver_account_id == receiver_id}
        slot = next(s for s in range(1, 10**6) if s not in usados)
        self.gifts.append(Gift(self._next, sender_id, receiver_id, slot, catalog_id, days))
        self._next += 1
        return True

    async def claim(self, gift: Gift, unit: ItemUnit) -> bool:
        if gift not in self.gifts:
            return False
        self.gifts.remove(gift)
        self.unidades.append(unit)
        return True

    async def items(self, account_id: int) -> list[ItemUnit]:
        return list(self.unidades)


def _gift_service(
    *, contas: tuple[Account, ...], progresso: FakeProgression
) -> tuple[GiftService, FakeGiftRepo]:
    repo = FakeGiftRepo(progresso)
    catalogo = FakeCatalog()
    servico = GiftService(
        catalog=catalogo,
        inventory=InventoryService(catalogo, clock=lambda: AGORA, new_guid=lambda: GUID),
        items=repo,
        accounts=FakeAccounts(*contas),
        progression=progresso,
        repository=repo,
    )
    return servico, repo


BIA = Account(id=2, username="bia", nickname="Bia", token_hash="h")
ANA = Account(id=1, username="ana", nickname="Ana", token_hash="h")


async def test_presente_debita_o_remetente_e_fica_pendente_para_o_destinatario() -> None:
    progresso = FakeProgression(ld=1000)
    servico, repo = _gift_service(contas=(BIA,), progresso=progresso)
    enviado = await servico.send(1, "Bia", ITEM, Currency.LD, 1)
    assert (enviado.receiver_id, enviado.price, enviado.days) == (2, 200, 7)
    assert progresso.ld == 800
    assert [(g.receiver_account_id, g.slot, g.duration_days) for g in repo.gifts] == [(2, 1, 7)]


async def test_nick_inexistente_recusa_sem_debitar() -> None:
    progresso = FakeProgression(ld=1000)
    servico, repo = _gift_service(contas=(BIA,), progresso=progresso)
    with pytest.raises(GiftRefusal) as recusa:
        await servico.send(1, "Ninguém", ITEM, Currency.LD, 0)
    assert recusa.value.result == -2407
    assert (progresso.ld, repo.gifts) == (1000, [])


async def test_presente_para_a_propria_conta_recusa() -> None:
    servico, repo = _gift_service(contas=(ANA,), progresso=FakeProgression(ld=1000))
    with pytest.raises(GiftRefusal) as recusa:
        await servico.send(1, "Ana", ITEM, Currency.LD, 0)
    assert recusa.value.result == 8000
    assert repo.gifts == []


async def test_morat_e_item_nao_vendido_na_moeda_nao_sao_presenteaveis() -> None:
    servico, repo = _gift_service(contas=(BIA,), progresso=FakeProgression(ld=99999))
    with pytest.raises(GiftRefusal) as morat:
        await servico.send(1, "Bia", 900, Currency.LD, 0)
    assert morat.value.result == 8000
    with pytest.raises(GiftRefusal) as sem_preco:
        await servico.send(1, "Bia", ITEM, Currency.CASH, 9)  # opção fora de 0 a 3
    assert sem_preco.value.result == 8000
    assert repo.gifts == []


async def test_saldo_insuficiente_usa_o_codigo_da_moeda() -> None:
    servico, _ = _gift_service(contas=(BIA,), progresso=FakeProgression(ld=50, cash=5))
    with pytest.raises(GiftRefusal) as ld:
        await servico.send(1, "Bia", ITEM, Currency.LD, 0)
    assert ld.value.result == -4056
    with pytest.raises(GiftRefusal) as cash:
        await servico.send(1, "Bia", ITEM, Currency.CASH, 0)
    assert cash.value.result == -4055


async def test_deposito_pagina_de_doze_e_nega_pagina_negativa() -> None:
    progresso = FakeProgression(ld=10**6)
    servico, repo = _gift_service(contas=(BIA,), progresso=progresso)
    for _ in range(13):
        await servico.send(1, "Bia", ITEM, Currency.LD, 0)
    primeira = await servico.page(2, 0)
    segunda = await servico.page(2, 1)
    assert [g.slot for g in primeira.gifts] == list(range(1, 13))
    assert [g.slot for g in segunda.gifts] == [13]
    assert (await servico.page(2, -1)).page == 0


async def test_resgate_grava_o_item_no_inventario_e_nao_repete() -> None:
    servico, repo = _gift_service(contas=(BIA,), progresso=FakeProgression(ld=1000))
    await servico.send(1, "Bia", ITEM, Currency.LD, 1)
    unidade = await servico.claim(2, 1)
    assert (unidade.catalog_id, unidade.inventory_index) == (ITEM, 1)
    assert unidade.expires_at == AGORA.replace(day=8)
    assert repo.gifts == []
    with pytest.raises(GiftRefusal) as de_novo:
        await servico.claim(2, 1)
    assert de_novo.value.result == 8000


async def test_resgate_de_chave_inexistente_recusa() -> None:
    servico, _ = _gift_service(contas=(BIA,), progresso=FakeProgression())
    with pytest.raises(GiftRefusal) as recusa:
        await servico.claim(2, 42)
    assert recusa.value.result == 8000


def test_enabled_gates_segue_a_contagem_e_os_morats_ocupados() -> None:
    assert enabled_gates(4, []) == (0, 1, 2, 3)
    assert enabled_gates(4, [5]) == (
        0,
        1,
        2,
        3,
        4,
        5,
    )  # morat antigo fora da contagem continua visível
    assert enabled_gates(6, [0]) == (0, 1, 2, 3, 4, 5)
    assert enabled_gates(99, []) == tuple(range(GATE_COUNT))


def test_sorteio_dá_ld_na_faixa_e_um_premio_do_conjunto_permitido() -> None:
    rng = random.Random(7)
    vistos: set[int] = set()
    for _ in range(300):
        ld, premio = draw(rng)
        assert ld.catalog_id == 0 and LD_MIN <= ld.ld <= LD_MAX and ld.ld % 1000 == 0
        assert premio.ld == 0
        assert premio.catalog_id in (*PAINTS, EXP_BOOST, *BOX_ITEMS)
        if premio.catalog_id in PAINTS:
            assert premio.days in (1, 7)
        else:
            assert premio.days == 1
        vistos.add(premio.catalog_id)
    assert len(vistos) > 5  # sorteio não é constante


def test_descricao_do_premio_com_prazo_e_ld() -> None:
    nomes = FakeCatalog()
    assert prize_of(Drop(0, 0, 5000), nomes).description == "5000 LD"
    pintura = prize_of(Drop(PAINTS[0], 7, 0), nomes)
    assert (pintura.item_id, pintura.buy_option) == (PAINTS[0], 1)
    assert pintura.description == "Pintura: Desert (7 dias)"
    assert prize_of(Drop(EXP_BOOST, 1, 0), nomes).description == f"Item {EXP_BOOST} (1 dia)"


@dataclass
class FakeUseRepo:
    chamadas: list[dict] = field(default_factory=list)
    aceita: bool = True

    async def consume(self, account_id, index, catalog_id, *, ld, grants, gate_count) -> bool:
        self.chamadas.append(
            {"index": index, "catalog": catalog_id, "ld": ld, "grants": grants, "gate": gate_count}
        )
        return self.aceita


@dataclass
class FakeItems:
    itens: list[ItemUnit]

    async def items(self, account_id: int) -> list[ItemUnit]:
        return list(self.itens)


def _unidade(index: int, catalog: int, *, montada: bool = False) -> ItemUnit:
    return ItemUnit(
        account_id=1,
        inventory_index=index,
        catalog_id=catalog,
        item_guid=f"{index:036d}",
        apply_flag=ApplyFlag.REALTIME,
        apply_value=None,
        expires_at=AGORA + timedelta(days=7),
        account_morat_id=7 if montada else None,
    )


def _uso(
    itens: list[ItemUnit], *, gates: int = 4, aceita: bool = True, agora: datetime = AGORA
) -> tuple[ItemUseService, FakeUseRepo]:
    repo = FakeUseRepo(aceita=aceita)
    catalogo = FakeCatalog()
    servico = ItemUseService(
        names=catalogo,
        inventory=InventoryService(catalogo, clock=lambda: AGORA, new_guid=lambda: GUID),
        items=FakeItems(itens),
        accounts=FakeAccounts(gates=gates),
        progression=FakeProgression(ld=777, cash=5),
        repository=repo,
        rng=random.Random(3),
        clock=lambda: agora,
    )
    return servico, repo


async def test_item_surpresa_consome_e_premia_com_ld_e_sorteio() -> None:
    servico, repo = _uso([_unidade(3, GACHA_ITEM)])
    aberto = await servico.use(1, 3)
    assert isinstance(aberto, GachaOpened)
    assert len(aberto.prizes) == 2 and aberto.prizes[0].item_id == 0
    assert (aberto.ld, aberto.cash) == (777, 5)
    chamada = repo.chamadas[0]
    assert (chamada["index"], chamada["catalog"], chamada["gate"]) == (3, GACHA_ITEM, None)
    assert chamada["ld"] == draw(random.Random(3))[0].ld  # mesma semente: o primeiro sorteio é o LD
    assert [u.catalog_id for u in chamada["grants"]] == [
        p.item_id for p in aberto.prizes if p.item_id
    ]


async def test_item_surpresa_sem_consumo_nao_premia() -> None:
    servico, _ = _uso([_unidade(3, GACHA_ITEM)], aceita=False)
    with pytest.raises(ItemRefusal) as recusa:
        await servico.use(1, 3)
    assert recusa.value.result == UseResult.DENIED


async def test_uso_de_outro_item_ou_montado_segue_para_o_equipar() -> None:
    servico, repo = _uso([_unidade(1, 201020001), _unidade(2, GACHA_ITEM, montada=True)])
    assert await servico.use(1, 1) is None
    assert await servico.use(1, 2) is None
    assert await servico.use(1, 99) is None
    assert repo.chamadas == []


async def test_item_vencido_segue_para_o_equipar_sem_abrir() -> None:
    servico, repo = _uso([_unidade(3, GACHA_ITEM)], agora=AGORA + timedelta(days=8))
    assert await servico.use(1, 3) is None
    assert repo.chamadas == []


async def test_adicionar_hangar_sobe_a_contagem_ate_oito() -> None:
    servico, repo = _uso([_unidade(4, ADD_GATE_ITEM)], gates=4)
    feito = await servico.use(1, 4)
    assert feito == GateAdded(index=4, gate_count=5)
    assert repo.chamadas[0]["gate"] == 5 and repo.chamadas[0]["ld"] == 0


async def test_adicionar_hangar_com_oito_gates_recusa_com_limite() -> None:
    servico, repo = _uso([_unidade(4, ADD_GATE_ITEM)], gates=GATE_COUNT)
    with pytest.raises(ItemRefusal) as recusa:
        await servico.use(1, 4)
    assert recusa.value.result == UseResult.GATE_LIMIT == -4083
    assert repo.chamadas == []
