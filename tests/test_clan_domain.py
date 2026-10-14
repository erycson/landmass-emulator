"""Regras de clã (F13) sem IO: nome, marca e saída do mestre."""

import pytest

from landmass_emu.domain.clan import ClanError, ClanRules


def test_nome_de_1_a_16_caracteres() -> None:
    rules = ClanRules()

    assert rules.check_name("A") == "A"
    assert rules.check_name("A" * 16) == "A" * 16
    with pytest.raises(ClanError, match="1 a 16"):
        rules.check_name("")
    with pytest.raises(ClanError, match="1 a 16"):
        rules.check_name("A" * 17)


def test_nome_precisa_caber_em_cp1252_e_nao_ter_nul() -> None:
    rules = ClanRules()

    assert rules.check_name("Praça") == "Praça"  # ç existe em cp1252
    with pytest.raises(ClanError, match="cp1252"):
        rules.check_name("Ж")
    with pytest.raises(ClanError, match="NUL"):
        rules.check_name("A\0B")


def test_marca_vai_como_i32() -> None:
    rules = ClanRules()

    assert rules.check_mark(0) == 0
    assert rules.check_mark(2**31 - 1) == 2**31 - 1
    with pytest.raises(ClanError):
        rules.check_mark(-1)
    with pytest.raises(ClanError):
        rules.check_mark(2**31)


def test_mestre_nao_sai_com_outros_membros() -> None:
    rules = ClanRules()

    with pytest.raises(ClanError, match="mestre"):
        rules.check_leave(is_master=True, member_count=2)
    rules.check_leave(is_master=True, member_count=1)  # sozinho, pode sair (clã é apagado)
    rules.check_leave(is_master=False, member_count=5)
