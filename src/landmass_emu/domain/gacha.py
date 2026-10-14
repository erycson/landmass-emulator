"""Item Surpresa (gacha, 308010006): sorteio puro. O uso (consumo e prêmio) é do `ItemUseService`.

Fonte da tabela: descrição do próprio item no wdb (`item_desc`, seção `XGame.LM_EtcItemI`): três
pinturas de 1 ou 7 dias, EXP+ de 1 dia, uma caixa de item aleatório de 1 dia e LD aleatório entre
1.000 e 500.000. Inferido: a descrição não diz a chance de cada um. Por isso cada abertura dá LD
sempre e um prêmio de sorte, com chance igual entre as cinco opções (decisão D-gacha-1).

A caixa sorteia entre os 12 itens de evento do `Item_Equip` com `item_buy_type` 1 e preço 0 (decisão
D-gacha-2; a descrição não lista os itens da caixa, e esta é a única lista de prêmios no wdb).
"""

import random
from dataclasses import dataclass
from typing import Protocol

from landmass_emu.domain.shop import DURATION_DAYS

LD_ITEM_ID = 0  # `item_id` 0 no LM_GATCHA_PRIZE é LD (LM_Engine.src)
PAINTS = (307010002, 307010003, 307010004)  # Desert, Splitter, Blackish
EXP_BOOST = 308020001  # Aumento de EXP
BOX_ITEMS = (
    201020001,
    201040002,
    201120001,
    201140001,
    204010003,
    204010004,
    204020003,
    204020004,
    204030003,
    204030004,
    204040003,
    204040004,
)
BOX_DAYS = 1
LD_MIN, LD_MAX, LD_STEP = 1000, 500000, 1000


@dataclass(frozen=True, slots=True)
class Drop:
    """Um sorteio: `catalog_id` 0 e `ld` > 0 é LD; senão é item de `days` dias."""

    catalog_id: int
    days: int
    ld: int


@dataclass(frozen=True, slots=True)
class Prize:
    """Registro `GACHA_PRIZE` (591): `item_id` 0 é LD, `size` 1, `buy_option` o índice do prazo
    (0 a 3, como a loja), e `description` o texto da tela."""

    item_id: int
    size: int
    buy_option: int
    description: str


class ItemNames(Protocol):
    def name(self, catalog_id: int) -> str | None: ...


def draw(rng: random.Random) -> tuple[Drop, Drop]:
    """LD (1.000 a 500.000, passo 1.000) e um prêmio de sorte, nesta ordem."""
    ld = Drop(catalog_id=0, days=0, ld=rng.randrange(LD_MIN, LD_MAX + 1, LD_STEP))
    kind = rng.randrange(len(PAINTS) + 2)  # três pinturas, EXP+ e caixa
    if kind < len(PAINTS):
        return ld, Drop(PAINTS[kind], rng.choice((1, 7)), 0)
    if kind == len(PAINTS):
        return ld, Drop(EXP_BOOST, BOX_DAYS, 0)
    return ld, Drop(rng.choice(BOX_ITEMS), BOX_DAYS, 0)


def prize_of(drop: Drop, names: ItemNames) -> Prize:
    """Texto e índice de prazo do sorteio, para o 591."""
    if drop.catalog_id == LD_ITEM_ID:
        return Prize(LD_ITEM_ID, 1, 0, f"{drop.ld} LD")
    name = names.name(drop.catalog_id) or f"Item {drop.catalog_id}"
    option = DURATION_DAYS.index(drop.days)
    return Prize(
        drop.catalog_id, 1, option, f"{name} ({drop.days} dia{'s' if drop.days > 1 else ''})"
    )
