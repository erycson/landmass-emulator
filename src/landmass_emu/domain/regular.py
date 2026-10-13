"""Morat regular (nest): validação da escolha do pedido 105. Regras puras, sem IO.

Fonte: `SetRegular(byte SelectNest, byte SelectMorats)` (dump de LM_Engine) e R-REG-01.
"""

from dataclasses import dataclass

# 1 Oddeye, 2 Shadow, 3 Leon.
NEST_RANGE = range(1, 4)
# 1 ASSAULT, 2 SNIPER, 3 DEFENDER, 4 ENGINEER. A classe 5 (SPECIAL) não é selecionável.
MORAT_CLASS_RANGE = range(1, 5)


@dataclass(frozen=True, slots=True)
class RegularChoice:
    nest: int
    morat_class: int


class RegularService:
    def choose(self, nest: int, morat_class: int) -> RegularChoice:
        if nest not in NEST_RANGE:
            raise ValueError(f"nest: de 1 a 3, veio {nest}")
        if morat_class not in MORAT_CLASS_RANGE:
            raise ValueError(f"classe regular: de 1 a 4, veio {morat_class}")
        # shortcut: exigir patente 'Praça' (SelectNestExp = 2800 exp, LevelList 'select_nest')
        # quando a F3 criar accounts.total_exp. Hoje não há exp para checar.
        return RegularChoice(nest, morat_class)
