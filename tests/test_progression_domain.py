from collections.abc import Callable
from pathlib import Path

import pytest

from landmass_emu.db.catalog import WdbCatalog
from landmass_emu.domain.progression import (
    MAX_I32,
    Grant,
    Level,
    Progression,
    ProgressionService,
    RankTable,
)
from landmass_emu.settings import Settings

# Início de LevelList do landmass.wdb (exp e nomes), e o platô final de R-LVL-04.
LEVELS = (
    Level(0, -1, "Sem Patente"),
    Level(1, 0, "Novato"),
    Level(2, 2800, "Praça"),
    Level(3, 5806, "Soldado 2ª Clas.1"),
    Level(4, 10470, "Soldado 2ª Clas.2"),
)
PLATEAU = (
    Level(93, MAX_I32, "Gen. de-Exército"),
    Level(94, MAX_I32, "Brigadeiro General"),
    Level(95, MAX_I32, "Marechal"),
)


def test_patente_fronteiras_do_inicio() -> None:
    ranks = RankTable(LEVELS)
    assert ranks.level_for(0).name == "Novato"  # nível 0 tem exp -1; nível 1 começa em 0
    assert ranks.level_for(2799).name == "Novato"
    assert ranks.level_for(2800).name == "Praça"
    assert ranks.level_for(5805).name == "Praça"
    assert ranks.level_for(5806).level == 3


def test_patente_platô_pega_o_ultimo_nivel_do_empate() -> None:
    ranks = RankTable((*LEVELS, *PLATEAU))
    assert ranks.level_for(MAX_I32).level == 95
    assert ranks.level_for(MAX_I32 - 1).level == 4
    assert ranks.level_for(10470).level == 4


def test_patente_rejeita_exp_negativa_e_tabela_invalida() -> None:
    with pytest.raises(ValueError):
        RankTable(LEVELS).level_for(-5)
    with pytest.raises(ValueError):
        RankTable(())
    with pytest.raises(ValueError):
        RankTable((Level(0, 100, "a"), Level(1, 50, "b")))


def test_patente_aceita_niveis_fora_de_ordem() -> None:
    assert RankTable(tuple(reversed(LEVELS))).level_for(2800).name == "Praça"


def test_tutorial_bit_por_passo() -> None:
    rules = ProgressionService()
    assert [rules.tutorial_bit(step) for step in range(3)] == [1, 2, 4]
    with pytest.raises(ValueError):
        rules.tutorial_bit(3)
    with pytest.raises(ValueError):
        rules.tutorial_bit(-1)


def test_check_grant_soma_e_preserva_o_tutorial() -> None:
    current = Progression(total_exp=100, ld=50, cash=7, tutorial_clear=5)
    totals = ProgressionService().check_grant(current, Grant(exp=2700, ld=1000, cash=500))
    assert totals == Progression(total_exp=2800, ld=1050, cash=507, tutorial_clear=5)


def test_check_grant_recusa_estouro_de_i32() -> None:
    rules = ProgressionService()
    near = Progression(total_exp=MAX_I32 - 10)
    assert rules.check_grant(near, Grant(exp=10)).total_exp == MAX_I32
    with pytest.raises(ValueError):
        rules.check_grant(near, Grant(exp=11))
    with pytest.raises(ValueError):
        rules.check_grant(Progression(ld=MAX_I32), Grant(ld=1))


def test_grant_rejeita_negativo_acima_de_i32_e_tudo_zero() -> None:
    with pytest.raises(ValueError):
        Grant(exp=-1, ld=5)
    with pytest.raises(ValueError):
        Grant(cash=MAX_I32 + 1)
    with pytest.raises(ValueError):
        Grant()
    assert Grant(cash=500) == Grant(exp=0, ld=0, cash=500)


def test_wdb_le_levellist_em_cp1252(wdb_de_teste: Callable[[], Path]) -> None:
    levels = WdbCatalog(wdb_de_teste()).level_list()
    assert levels == (Level(1, 0, "Novato"), Level(2, 2800, "Praça"))


def test_wdb_ausente_levanta_valueerror(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="não encontrado"):
        WdbCatalog(tmp_path / "nao_existe.wdb").level_list()


def test_wdb_real_do_cliente_quando_disponivel() -> None:
    """Confere a tabela real: `LANDMASS_CLIENT_DIR` aponta para a pasta `system` do cliente."""
    real = Settings(_env_file=None).client_dir / "landmass.wdb"
    if not real.is_file():
        pytest.skip(f"landmass.wdb ausente em {real}; defina LANDMASS_CLIENT_DIR")
    levels = WdbCatalog(real).level_list()
    assert len(levels) == 101
    ranks = RankTable(levels)
    assert ranks.level_for(0).name == "Novato"
    assert ranks.level_for(2800).level == 2
    assert ranks.level_for(2800).name == "Praça"
