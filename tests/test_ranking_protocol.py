"""Codec de 171 (ranking, F14): offsets que `NotifyRankingInfo` lê no cliente (re/protocol_full.md
§2.2; re/LM_Engine.dll/NotifyRankingInfo_0x10003e30.c)."""

import struct

import pytest

from landmass_emu.protocol.message import MsRankingInfoOut, RankingEntry


def _entradas(body: bytes) -> list[tuple[int, int, bytes, int, int]]:
    """Lê o corpo do jeito que o cliente lê: entradas de 0x20 a partir de @0."""
    out = []
    for off in range(0, len(body), 0x20):
        index, rank = struct.unpack_from("<iH", body, off)
        nick = body[off + 6 : off + 0x18].split(b"\0", 1)[0]
        total_exp, clan = struct.unpack_from("<iH", body, off + 0x18)
        out.append((index, rank, nick, total_exp, clan))
    return out


def test_entrada_tem_offsets_do_cliente() -> None:
    body = MsRankingInfoOut((RankingEntry(0, 1, "Ana", 2800, 7),)).pack()

    assert len(body) == 0x40  # uma entrada e a sentinela
    assert _entradas(body)[0] == (0, 1, b"Ana", 2800, 7)


def test_sentinela_zera_rank_quando_ha_menos_de_100() -> None:
    body = MsRankingInfoOut((RankingEntry(0, 1, "Ana", 10, 0),)).pack()

    assert _entradas(body)[1][1] == 0  # rank 0 encerra o laço do cliente


def test_lista_cheia_nao_leva_sentinela() -> None:
    entradas = tuple(RankingEntry(i, i + 1, f"c{i}", 100 - i) for i in range(100))
    body = MsRankingInfoOut(entradas).pack()

    assert len(body) == 100 * 0x20
    assert all(rank != 0 for _, rank, *_ in _entradas(body))


def test_empate_leva_a_mesma_posicao_e_slot_sequencial() -> None:
    body = MsRankingInfoOut(
        (
            RankingEntry(0, 1, "A", 500),
            RankingEntry(1, 1, "B", 500),
            RankingEntry(2, 3, "C", 300),
        )
    ).pack()

    assert [(i, r) for i, r, *_ in _entradas(body)[:3]] == [(0, 1), (1, 1), (2, 3)]


def test_nick_de_16_caracteres_cabe_com_nul() -> None:
    body = MsRankingInfoOut((RankingEntry(0, 1, "A" * 16, 1),)).pack()

    assert body[6:22] == b"A" * 16
    assert body[22] == 0  # NUL em @0x16, dentro da entrada


def test_nick_maior_que_16_e_truncado() -> None:
    body = MsRankingInfoOut((RankingEntry(0, 1, "B" * 40, 1),)).pack()

    assert body[6:22] == b"B" * 16
    assert body[22] == 0


def test_rank_zero_e_recusado() -> None:
    with pytest.raises(ValueError, match="maior que zero"):
        MsRankingInfoOut((RankingEntry(0, 0, "A", 1),)).pack()


def test_mais_de_100_linhas_sao_recusadas() -> None:
    entradas = tuple(RankingEntry(i % 100, 1, "A", 1) for i in range(101))
    with pytest.raises(ValueError, match="máximo 100"):
        MsRankingInfoOut(entradas).pack()


def test_lista_vazia_leva_so_a_sentinela() -> None:
    body = MsRankingInfoOut(()).pack()

    assert body == bytes(0x20)
