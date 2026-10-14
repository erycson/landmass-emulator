"""Aviso geral do canal (251): layout, limite do cliente e envio a todo o lobby."""

import logging

import pytest

from landmass_emu.domain.lobby import Lobby
from landmass_emu.handlers.channel.notice import GlobalNotice
from landmass_emu.protocol.header import CHANNEL_NET_CODE, unpack_header
from landmass_emu.protocol.notice import MAX_NOTICE_BYTES, NOTICE_OPCODE, CsSendCommandOut


class _Recebedor:
    def __init__(self) -> None:
        self.corpos: list[bytes] = []

    def send(self, body: bytes) -> None:
        self.corpos.append(body)


def test_layout_e_u8_de_tamanho_seguido_do_texto() -> None:
    assert CsSendCommandOut(b"Oi").pack() == b"\x02Oi"
    assert CsSendCommandOut(b"x" * MAX_NOTICE_BYTES).pack()[0] == MAX_NOTICE_BYTES


def test_limite_e_o_do_cliente_120_bytes() -> None:
    assert MAX_NOTICE_BYTES == 120
    with pytest.raises(ValueError, match="121 bytes"):
        CsSendCommandOut(b"x" * 121).pack()


def test_texto_vazio_e_erro() -> None:
    with pytest.raises(ValueError, match="0 bytes"):
        CsSendCommandOut(b"").pack()


def test_envio_chega_a_todo_o_lobby_com_opcode_251() -> None:
    lobby = Lobby()
    ana, bia = _Recebedor(), _Recebedor()
    lobby.join(7, ana, "Ana")
    lobby.join(9, bia, "Bia")

    GlobalNotice(lobby).send("Manutenção.")

    for recebedor in (ana, bia):
        [corpo] = recebedor.corpos
        header, payload = unpack_header(corpo)
        assert (header.opcode, header.net_code) == (NOTICE_OPCODE, CHANNEL_NET_CODE)
        texto = "Manutenção.".encode("cp1252")
        assert payload == bytes([len(texto)]) + texto


def test_texto_fora_do_cp1252_vira_interrogacao() -> None:
    lobby = Lobby()
    ana = _Recebedor()
    lobby.join(7, ana, "Ana")
    GlobalNotice(lobby).send("Olá 漢")
    _, payload = unpack_header(ana.corpos[0])
    texto = "Olá ?".encode("cp1252")
    assert payload == bytes([len(texto)]) + texto


def test_texto_longo_e_cortado_com_aviso_no_log(caplog: pytest.LogCaptureFixture) -> None:
    lobby = Lobby()
    ana = _Recebedor()
    lobby.join(7, ana, "Ana")
    with caplog.at_level(logging.WARNING, logger="landmass_emu.handlers.channel.notice"):
        GlobalNotice(lobby).send("a" * 150)
    _, payload = unpack_header(ana.corpos[0])
    assert payload == bytes([MAX_NOTICE_BYTES]) + b"a" * MAX_NOTICE_BYTES
    assert "aviso cortado de 150 para 120 bytes" in caplog.text


def test_aviso_vazio_nao_sai() -> None:
    with pytest.raises(ValueError, match="aviso vazio"):
        GlobalNotice(Lobby()).send("")
