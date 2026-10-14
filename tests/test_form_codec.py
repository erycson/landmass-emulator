import random
import struct

import pytest

from landmass_emu.protocol.form_codec import FormCodec, FormCodecError
from landmass_emu.protocol.message import MsLoginIn

# Vetores conferidos à mão contra o pseudocódigo de FUN_10028120 (LM_Engine.dll, 0x10028120):
# caractere n = alfabeto[rotação à esquerda de 6 bits por (n + 1) % 6], preenchimento '9'.
VETORES = [
    (b"a", b"CR99"),
    (b"ab", b"CXR9"),
    (b"abc", b"CXbJ"),
]


@pytest.mark.parametrize(("raw", "encoded"), VETORES)
def test_vetores_do_cliente(raw: bytes, encoded: bytes) -> None:
    assert FormCodec.encode(raw) == encoded
    assert FormCodec.decode(encoded) == raw


def test_tamanho_codificado_e_4_por_3_arredondado_para_cima() -> None:
    for n in range(0, 33):
        assert len(FormCodec.encode(b"x" * n)) == 4 * -(-n // 3)


def test_ida_e_volta_com_bytes_arbitrarios() -> None:
    rnd = random.Random(7)
    for _ in range(500):
        raw = bytes(rnd.randrange(256) for _ in range(rnd.randrange(0, 33)))
        assert FormCodec.decode(FormCodec.encode(raw)) == raw


def test_campo_fora_do_formato_e_recusado() -> None:
    with pytest.raises(FormCodecError):
        FormCodec.decode(b"CXR")  # tamanho não múltiplo de 4
    with pytest.raises(FormCodecError):
        FormCodec.decode(b"C999")  # três pads: sobra um caractere sem byte
    with pytest.raises(FormCodecError):
        FormCodec.decode("C\xe7R9".encode("latin-1"))  # não ASCII
    with pytest.raises(FormCodecError):
        FormCodec.decode(b"CX@9")  # '@' fora do alfabeto


def test_login_por_formulario_tem_campos_nos_offsets_do_cliente() -> None:
    # Layout de MS_LOGIN_IN no cliente: id_len @0, pw_len @4, login_num @8, forced @42.
    payload = MsLoginIn(login_num="", user_id="ab", password="a", forced=True).pack()
    id_len, pw_len = struct.unpack_from("<ii", payload)
    assert (id_len, pw_len) == (4, 4)
    assert payload[42] == 1
    assert payload[44:48] == b"CXR9"  # id codificado logo após o cabeçalho de 44 bytes
    assert payload[48:52] == b"CR99"  # senha codificada
    assert MsLoginIn.unpack(payload) == MsLoginIn(
        login_num="", user_id="ab", password="a", forced=True
    )


def test_login_por_guid_nao_tem_id_nem_senha() -> None:
    payload = MsLoginIn(login_num="0123456789abcdef0123456789abcdef").pack()
    assert len(payload) == 44
    assert struct.unpack_from("<ii", payload) == (0, 0)
    assert payload[42] == 0
