"""`LMEmu.ini`: uma seção por partida, troca da mesma chave, outras seções preservadas byte a byte e
remoção sem tocar nas demais (D190)."""

import logging
from pathlib import Path

import pytest

from landmass_emu.hosting.loadout import LoadoutFile


def test_escreve_a_secao_com_uma_linha_players_por_jogador(tmp_path: Path) -> None:
    LoadoutFile(tmp_path / "LMEmu.ini").write(
        "m00000001", ["0041006E0061|?Team=0", "0042006F0062|?Team=1"]
    )

    assert (tmp_path / "LMEmu.ini").read_bytes() == (
        b"[m00000001 LMEmuLoadout]\r\n"
        b"Players=0041006E0061|?Team=0\r\n"
        b"Players=0042006F0062|?Team=1\r\n"
    )


def test_duas_partidas_e_remocao_de_uma_mantem_a_outra(tmp_path: Path) -> None:
    arquivo = LoadoutFile(tmp_path / "LMEmu.ini")
    arquivo.write("m00000001", ["a|?Team=0"])
    arquivo.write("m00000002", ["b|?Team=1"])

    arquivo.remove("m00000001")

    assert (tmp_path / "LMEmu.ini").read_bytes() == (
        b"[m00000002 LMEmuLoadout]\r\nPlayers=b|?Team=1\r\n"
    )


def test_gravar_a_mesma_chave_troca_a_secao(tmp_path: Path) -> None:
    arquivo = LoadoutFile(tmp_path / "LMEmu.ini")
    arquivo.write("m00000001", ["antiga|?Team=0"])

    arquivo.write("m00000001", ["nova|?Team=1"])

    assert (tmp_path / "LMEmu.ini").read_bytes() == (
        b"[m00000001 LMEmuLoadout]\r\nPlayers=nova|?Team=1\r\n"
    )


def test_outras_secoes_voltam_byte_a_byte(tmp_path: Path) -> None:
    original = b"[LMEmu.Outra]\r\nChave=\xe7\xe3\r\n[LMEmu.Mais]\r\nSolta=1\r\n"
    (tmp_path / "LMEmu.ini").write_bytes(original)
    arquivo = LoadoutFile(tmp_path / "LMEmu.ini")

    arquivo.write("m00000001", ["x|?Team=0"])
    assert (tmp_path / "LMEmu.ini").read_bytes().startswith(original)

    arquivo.remove("m00000001")
    assert (tmp_path / "LMEmu.ini").read_bytes() == original


def test_texto_com_acento_sai_em_cp1252(tmp_path: Path) -> None:
    LoadoutFile(tmp_path / "LMEmu.ini").write("m00000001", ["ç|?Team=0"])

    assert b"Players=\xe7|?Team=0\r\n" in (tmp_path / "LMEmu.ini").read_bytes()


def test_remocao_sem_arquivo_nao_cria_nada(tmp_path: Path) -> None:
    LoadoutFile(tmp_path / "LMEmu.ini").remove("m00000001")

    assert not (tmp_path / "LMEmu.ini").exists()


def test_remocao_da_ultima_secao_deixa_arquivo_vazio(tmp_path: Path) -> None:
    arquivo = LoadoutFile(tmp_path / "LMEmu.ini")
    arquivo.write("m00000001", ["a|?Team=0"])

    arquivo.remove("m00000001")

    assert (tmp_path / "LMEmu.ini").read_bytes() == b""


def test_falha_de_gravacao_levanta_oserror(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        LoadoutFile(tmp_path / "pasta_ausente" / "LMEmu.ini").write("m00000001", ["a|?Team=0"])


def test_falha_na_remocao_so_vai_ao_log(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    (tmp_path / "LMEmu.ini").mkdir()  # caminho que não é arquivo: a leitura falha

    with caplog.at_level(logging.WARNING):
        LoadoutFile(tmp_path / "LMEmu.ini").remove("m00000001")

    assert "não removida" in caplog.text
