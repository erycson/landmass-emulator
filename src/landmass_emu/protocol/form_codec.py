"""Codec de id e senha do formulário de login (`MS_LOGIN_IN` com id_len > 0).

O cliente não manda o texto puro: `FUN_10025F40` (LM_Engine.dll, 0x10025F40) passa id e senha por
`FUN_10028120` (0x10028120), um base64 com alfabeto próprio. Cada caractere de saída `n` (base 0)
é o valor de 6 bits rotacionado à esquerda `(n + 1) % 6` posições, indexado no alfabeto. O
preenchimento é o caractere `9` (índice 64). Evidência em tools/re/message_server.md (§5.1).
"""

ALPHABET = "MRjxSTYZab67uvQc!N8U#OwVWX5Pkst4defghiyz0G23lmnHCqr=DEFIJKL1opAB"
PAD = "9"
_MAX_PAD = 2


class FormCodecError(ValueError):
    """Campo de formulário fora do formato do cliente."""


class FormCodec:
    @staticmethod
    def encode(raw: bytes) -> bytes:
        out = "".join(ALPHABET[_rotl6(value, (n + 1) % 6)] for n, value in enumerate(_split6(raw)))
        return (out + PAD * ((-len(out)) % 4)).encode("ascii")

    @staticmethod
    def decode(encoded: bytes) -> bytes:
        try:
            text = encoded.decode("ascii")
        except UnicodeDecodeError as e:
            raise FormCodecError("campo de formulário não é ASCII") from e
        data = text.rstrip(PAD)
        pads = len(text) - len(data)
        if len(text) % 4 or pads > _MAX_PAD:
            raise FormCodecError("campo de formulário com tamanho inválido")
        values = []
        for n, char in enumerate(data):
            index = ALPHABET.find(char)
            if index < 0:
                raise FormCodecError("campo de formulário com caractere fora do alfabeto")
            values.append(_rotr6(index, (n + 1) % 6))
        return _join6(values)


def _split6(raw: bytes) -> list[int]:
    """Bytes em grupos de 6 bits, com zeros à direita no último grupo."""
    bits = 0
    count = 0
    values: list[int] = []
    for byte in raw:
        bits = (bits << 8) | byte
        count += 8
        while count >= 6:
            count -= 6
            values.append((bits >> count) & 0x3F)
    if count:
        values.append((bits << (6 - count)) & 0x3F)
    return values


def _join6(values: list[int]) -> bytes:
    """Grupos de 6 bits de volta a bytes. Bits sobrando no fim são descartados."""
    bits = 0
    count = 0
    out = bytearray()
    for value in values:
        bits = (bits << 6) | value
        count += 6
        if count >= 8:
            count -= 8
            out.append((bits >> count) & 0xFF)
    return bytes(out)


def _rotl6(value: int, shift: int) -> int:
    return ((value << shift) | (value >> (6 - shift))) & 0x3F


def _rotr6(value: int, shift: int) -> int:
    return _rotl6(value, (6 - shift) % 6)
