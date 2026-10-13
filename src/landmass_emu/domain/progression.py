"""Progressão e economia: experiência, saldos, tutorial e patente. Regras puras, sem IO.

Fonte: docs/architecture/07-progression.md §5.1 (moedas), §5.8 (patente) e §5.10 (tutorial).
"""

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

# Limite dos campos `i32` do registro do jogador (101) e dos pushes de saldo (900, 902).
MAX_I32 = 2**31 - 1
TUTORIAL_STEPS = 3


@dataclass(frozen=True, slots=True)
class Progression:
    total_exp: int = 0
    ld: int = 0
    cash: int = 0
    tutorial_clear: int = 0


@dataclass(frozen=True, slots=True)
class Grant:
    """Concessão pela CLI. Valores ≥ 0 (R-MON-01: saldo nunca negativo)."""

    exp: int = 0
    ld: int = 0
    cash: int = 0

    def __post_init__(self) -> None:
        for name, value in (("exp", self.exp), ("ld", self.ld), ("cash", self.cash)):
            if not 0 <= value <= MAX_I32:
                raise ValueError(f"{name}: valor fora de 0 a {MAX_I32}")
        if self.exp == self.ld == self.cash == 0:
            raise ValueError("nada a conceder: informe --exp, --ld ou --cash")


@dataclass(frozen=True, slots=True)
class Level:
    level: int
    exp: int
    name: str


class RankTable:
    """Patente: maior nível `n` com `total_exp >= exp[n]` (R-LVL-01).

    A tabela vem de `LevelList` do `landmass.wdb` (D7). `exp` é não decrescente; os níveis
    altos repetem o mesmo valor (R-LVL-04), e a busca pega o último deles.
    """

    def __init__(self, levels: Sequence[Level]) -> None:
        ordered = tuple(sorted(levels, key=lambda lv: lv.level))
        if not ordered:
            raise ValueError("tabela de níveis vazia")
        if any(a.exp > b.exp for a, b in pairwise(ordered)):
            raise ValueError("LevelList fora de ordem: exp decresce")
        self._levels = ordered
        self._exps = [lv.exp for lv in ordered]

    def level_for(self, total_exp: int) -> Level:
        index = bisect_right(self._exps, total_exp) - 1
        if index < 0:
            raise ValueError(f"experiência {total_exp} abaixo do primeiro nível")
        return self._levels[index]


class ProgressionService:
    """Regras de progressão que não pertencem a um repositório."""

    def tutorial_bit(self, step: int) -> int:
        """Bit do passo: 0 movimento (0x1), 1 tiro (0x2), 2 engenheiro (0x4). R-TUT-01."""
        if not 0 <= step < TUTORIAL_STEPS:
            raise ValueError(f"passo de tutorial fora de 0 a {TUTORIAL_STEPS - 1}: {step}")
        return 1 << step

    def check_grant(self, current: Progression, grant: Grant) -> Progression:
        """Totais depois da concessão. Recusa o que passaria de i32: o 101 não sairia e o login
        travaria, porque `_dispatch` engole o `struct.error` sem resposta."""
        totals = Progression(
            total_exp=current.total_exp + grant.exp,
            ld=current.ld + grant.ld,
            cash=current.cash + grant.cash,
            tutorial_clear=current.tutorial_clear,
        )
        for name, value in (
            ("exp", totals.total_exp),
            ("LD", totals.ld),
            ("Cash", totals.cash),
        ):
            if value > MAX_I32:
                raise ValueError(f"{name} resultante {value} passa de {MAX_I32}")
        return totals
