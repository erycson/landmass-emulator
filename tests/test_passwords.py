import pytest

from landmass_emu.domain.passwords import PASSWORD_MAX_BYTES, PasswordHasher, check_password


def test_senha_confere_e_erra() -> None:
    guardada = PasswordHasher.hash("Segredo1")
    assert PasswordHasher.verify("Segredo1", guardada)
    assert not PasswordHasher.verify("segredo1", guardada)
    assert not PasswordHasher.verify("Segredo1 ", guardada)


def test_mesma_senha_gera_hashes_diferentes_pelo_sal() -> None:
    a = PasswordHasher.hash("mesma")
    b = PasswordHasher.hash("mesma")
    assert a != b
    assert PasswordHasher.verify("mesma", a) and PasswordHasher.verify("mesma", b)


def test_formato_guardado_traz_os_parametros() -> None:
    partes = PasswordHasher.hash("x").split("$")
    assert partes[:4] == ["scrypt", "16384", "8", "1"]
    assert len(partes[4]) == 32 and len(partes[5]) == 64


@pytest.mark.parametrize("ruim", ["", "scrypt$1$2$3", "md5$16384$8$1$00$00", "scrypt$x$8$1$00$00"])
def test_hash_corrompido_ou_de_outro_esquema_recusa(ruim: str) -> None:
    assert not PasswordHasher.verify("qualquer", ruim)


def test_senha_limites_em_cp1252() -> None:
    check_password("a")
    check_password("a" * PASSWORD_MAX_BYTES)
    with pytest.raises(ValueError, match="de 1 a 32"):
        check_password("")
    with pytest.raises(ValueError, match="de 1 a 32"):
        check_password("a" * (PASSWORD_MAX_BYTES + 1))
    with pytest.raises(ValueError, match="cp1252"):
        check_password("senha✓")  # U+2713 não existe em cp1252 (o € existe)
