"""Mensagens do Channel Server (porta 7314, net_code 14). Layouts: re/channel_server.md (§2, §3.1).

Offsets são do corpo (depois do cabeçalho `u16`). Campo sem nome no RE recebe o nome do offset.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar

from landmass_emu.protocol.message import cstr

# Texto de chat: o cliente descarta `len > 0x78` (dispatch, opcode 241).
MAX_CHAT_TEXT = 0x78

# shortcut: lobby limitado a 1600 entradas por quadro (2 + 40*1600 cabe em 65000 bytes); quando
# max_clients passar disso, paginar a lista (opcodes 545/546 do cliente, layout não decodificado).
MAX_LOBBY_ENTRIES = 1600


class CsOp(IntEnum):
    HEARTBEAT = 2
    IN_CHANNEL_SERVER = 100
    IN_CHANNEL_SERVER_OUT = 101
    CHANNEL_INFO_OUT = 111
    IN_CHANNEL = 120
    IN_CHANNEL_OUT = 121
    OUT_CHANNEL = 122
    OUT_CHANNEL_OUT = 123
    CHANNEL_ROOM_INFO_OUT = 141
    CHANNEL_PLAYER_INFO_OUT = 151
    SEND_MESSAGE = 240
    SEND_MESSAGE_OUT = 241


@dataclass(frozen=True, slots=True)
class CsHeartbeat:
    """HEARTBEAT (2), servidor → cliente, corpo vazio. O cliente responde 2; o servidor ignora."""

    opcode: ClassVar[int] = CsOp.HEARTBEAT

    def pack(self) -> bytes:
        return b""


@dataclass(frozen=True, slots=True)
class CsInChannelServerIn:
    """IN_CHANNEL_SERVER (100): `char session_key[33]` @0 (32 hex + NUL).

    Evidência: no teste com o cliente real, o 100 chegou com 33 bytes zerados, depois de um 111 com
    33 bytes zerados. O 111 copia 33 bytes para `DAT_1005AE20` (re/message_server.md §4). Inferido:
    esses são os bytes de chave que o cliente devolve no 100. Não testado: o cliente aceitar uma
    chave não zerada."""

    session_key: str
    _SIZE = 33

    @classmethod
    def unpack(cls, payload: bytes) -> CsInChannelServerIn:
        if len(payload) < cls._SIZE:
            raise ValueError(f"CS_IN_CHANNEL_SERVER_IN curto: {len(payload)} bytes")
        return cls(cstr(payload[: cls._SIZE]))


@dataclass(frozen=True, slots=True)
class CsInChannelServerOut:
    """IN_CHANNEL_SERVER_OUT (101): corpo de 176 bytes.

    @0x00..0xa7: registro do próprio jogador (168 bytes), zeros exceto o id em @0x90 e @0xa0
    (o cliente lê o id de @0x90 como `DAT_1005ada0` e usa @0xa0 como chave do nó).
    @0xa8: `i32 result` (0 = ok). @0xac: `i32 location` (lido como `_DAT_1005ae08`; semântica
    não confirmada, o evento recebe `byte location`).

    shortcut: location fixo em 0 e `result` -160 para token recusado; confirmar no cliente real."""

    client_guid: int
    result: int
    location: int = 0
    opcode: ClassVar[int] = CsOp.IN_CHANNEL_SERVER_OUT
    _FIXED = struct.Struct("<144xi12xi4xii")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.client_guid, self.client_guid, self.result, self.location)


@dataclass(frozen=True, slots=True)
class CsChannelPlayer:
    """Entrada de jogador do lobby: 40 bytes. Stride da lista de 151 (a partir de @2); o corpo de
    121 é esta mesma entrada em @0 (o cliente lê até @0x24).

    Offsets dentro da entrada; o nó do cliente é +0x3c (at04), +0x10 (at08), +0x14 (at0c),
    +0x18 (at10), +0x1c (at14), +0x20 (at18), +0x23 (at19), +0x21 (at1a), +0x28 (at1c),
    +0x2c (at20), +0x30 (at24).

    shortcut: sem campo de nickname (nenhum decodificado em 121/151; candidatos 543 e 548); o
    lobby mostra entradas sem nome até decodificar. Revisar no cliente real."""

    client_guid: int
    at04: int = 0
    at08: int = 0
    at0c: int = 0
    at10: int = 0
    at14: int = 0
    at18: int = 0
    at19: int = 0
    at1a: int = 0
    at1c: int = 0
    at20: int = 0
    at24: int = 0
    _FIXED = struct.Struct("<iiiiiiBBBxiiB3x")

    def pack(self) -> bytes:
        return self._FIXED.pack(
            self.client_guid,
            self.at04,
            self.at08,
            self.at0c,
            self.at10,
            self.at14,
            self.at18,
            self.at19,
            self.at1a,
            self.at1c,
            self.at20,
            self.at24,
        )


@dataclass(frozen=True, slots=True)
class CsInChannelOut:
    """IN_CHANNEL_OUT (121): a entrada do jogador no lobby (corpo = `CsChannelPlayer`)."""

    player: CsChannelPlayer
    opcode: ClassVar[int] = CsOp.IN_CHANNEL_OUT

    def pack(self) -> bytes:
        return self.player.pack()


@dataclass(frozen=True, slots=True)
class CsChannelInfoOut:
    """CHANNEL_INFO_OUT (111): `u8 count` @0.

    shortcut: count fixo em 1 (o servidor original tem `channel_count 1`) e entrada sem corpo;
    o cliente não lê o corpo da entrada (`FUN_1001c170`). Revisar se o cliente pedir o nome do
    canal, e conferir no cliente real se a entrada aparece."""

    opcode: ClassVar[int] = CsOp.CHANNEL_INFO_OUT

    def pack(self) -> bytes:
        return b"\x01"


@dataclass(frozen=True, slots=True)
class CsChannelRoomInfoOut:
    """CHANNEL_ROOM_INFO_OUT (141): `u16 count` @0 = 0, lista de salas vazia. Entradas não
    decodificadas (layout de sala é do marco 3)."""

    opcode: ClassVar[int] = CsOp.CHANNEL_ROOM_INFO_OUT

    def pack(self) -> bytes:
        return b"\x00\x00"


@dataclass(frozen=True, slots=True)
class CsChannelPlayerInfoOut:
    """CHANNEL_PLAYER_INFO_OUT (151): `u16 count` @0 e `count` entradas de 40 bytes em @2."""

    players: tuple[CsChannelPlayer, ...]
    opcode: ClassVar[int] = CsOp.CHANNEL_PLAYER_INFO_OUT
    _COUNT = struct.Struct("<H")

    def pack(self) -> bytes:
        if len(self.players) > MAX_LOBBY_ENTRIES:
            raise ValueError(f"lobby com entradas demais para um quadro: {len(self.players)}")
        return self._COUNT.pack(len(self.players)) + b"".join(p.pack() for p in self.players)


@dataclass(frozen=True, slots=True)
class CsOutChannelOut:
    """OUT_CHANNEL_OUT (123): `i32 client_guid` @0, `u8 message` @4, padding @5..7. Total 8."""

    client_guid: int
    message: int = 0
    opcode: ClassVar[int] = CsOp.OUT_CHANNEL_OUT
    _FIXED = struct.Struct("<iB3x")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.client_guid, self.message)


@dataclass(frozen=True, slots=True)
class CsSendMessageIn:
    """SEND_MESSAGE (240): `u8 msg_type` @0, `u8 len` @1, texto[len] @2. Texto em bytes."""

    msg_type: int
    text: bytes
    _HEAD = struct.Struct("<BB")

    @classmethod
    def unpack(cls, payload: bytes) -> CsSendMessageIn:
        msg_type, length = cls._HEAD.unpack_from(payload)
        if length > MAX_CHAT_TEXT or len(payload) < 2 + length:
            raise ValueError(f"CS_SEND_MESSAGE_IN inconsistente: len={length}")
        return cls(msg_type, payload[2 : 2 + length])


@dataclass(frozen=True, slots=True)
class CsSendMessageOut:
    """SEND_MESSAGE_OUT (241): `i32 sender` @0, `u8 msg_type` @4, `u8 len` @5, padding @6..7,
    texto[len] @8. Sem NUL final.

    shortcut: `msg_type` (240 @0 e 241 @4) e padding @6..7 são inferidos da assinatura do evento;
    confirmar no cliente real se o chat mostra o tipo certo e se o eco ao remetente duplica."""

    sender: int
    msg_type: int
    text: bytes
    opcode: ClassVar[int] = CsOp.SEND_MESSAGE_OUT
    _HEAD = struct.Struct("<iBBxx")

    def pack(self) -> bytes:
        if len(self.text) > MAX_CHAT_TEXT:
            raise ValueError(f"mensagem longa demais: {len(self.text)} bytes")
        return self._HEAD.pack(self.sender, self.msg_type, len(self.text)) + self.text
