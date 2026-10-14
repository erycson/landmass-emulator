"""Mensagens do Message Server (porta 7313). Layouts em re/message_server.md (§4, §5)."""

import struct
from dataclasses import astuple, dataclass
from enum import IntEnum
from typing import ClassVar

ENCODING = "cp1252"


class MsOp(IntEnum):
    HEARTBEAT = 2
    LOGIN = 100
    LOGIN_OUT = 101
    REGISTER = 110
    REGISTER_OUT = 111
    IN_MESSAGE_SERVER = 120
    IN_MESSAGE_SERVER_OUT = 121
    GET_CHANNEL_SERVER_INFO = 130
    GET_CHANNEL_SERVER_OUT = 131
    CREATE_NICKNAME = 150
    SEND_WHISPER = 160
    SEND_WHISPER_OUT = 161
    SEND_WHISPER_ERROR_OUT = 162
    GET_FRIEND_LIST = 180
    ADD_FRIEND = 181
    DEL_FRIEND = 182
    FRIEND_LIST_OUT = 183
    DEL_FRIEND_OUT = 184
    ADD_BLACK = 186
    DEL_BLACK = 187
    BLACK_LIST_OUT = 188
    DEL_BLACK_OUT = 189
    REFRESH_FRIEND = 190
    REFRESH_FRIEND_OUT = 191
    REFRESH_BLACK = 192
    REFRESH_BLACK_OUT = 193


class MsResult(IntEnum):
    """Códigos de `msg_error` do cliente (`landmass.wdb`, tabela `msg_error`)."""

    OK = 0
    INVALID_VALUE = -11  # "Erro do valor inserido."
    CONTACT_OFFLINE = -19  # "Contato está offline."
    INVALID_PASSWORD = -160


def cstr(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode(ENCODING, errors="replace")


def cfield(text: str, size: int) -> bytes:
    """`char[size]` terminado em NUL. Texto que não cabe com o NUL é truncado."""
    return text.encode(ENCODING, errors="replace")[: size - 1].ljust(size, b"\0")


@dataclass(frozen=True, slots=True)
class MsLoginIn:
    """MS_LOGIN_IN: i32 id_len, i32 pw_len, char login_num[33] (+3 padding), id, pw."""

    login_num: str
    user_id: str = ""
    password: str = ""

    _FIXED = struct.Struct("<ii33s3x")

    @classmethod
    def unpack(cls, payload: bytes) -> MsLoginIn:
        id_len, pw_len, guid = cls._FIXED.unpack_from(payload)
        if id_len < 0 or pw_len < 0 or cls._FIXED.size + id_len + pw_len > len(payload):
            raise ValueError(f"MS_LOGIN_IN inconsistente: id_len={id_len} pw_len={pw_len}")
        off = cls._FIXED.size
        return cls(
            login_num=cstr(guid),
            user_id=cstr(payload[off : off + id_len]),
            password=cstr(payload[off + id_len : off + id_len + pw_len]),
        )

    def pack(self) -> bytes:
        uid = self.user_id.encode(ENCODING)
        pw = self.password.encode(ENCODING)
        return self._FIXED.pack(len(uid), len(pw), self.login_num.encode(ENCODING)) + uid + pw


@dataclass(frozen=True, slots=True)
class MsLoginOut:
    """MS_LOGIN_OUT (101): u8 forced_login @0 (0), padding @1..3, i32 result @4. Total 8."""

    result: int
    opcode: ClassVar[int] = MsOp.LOGIN_OUT

    _FIXED = struct.Struct("<B3xi")

    def pack(self) -> bytes:
        return self._FIXED.pack(0, self.result)


@dataclass(frozen=True, slots=True)
class LmRegisterInfo:
    """LM_REGISTER_INFO: 37 bytes u8, nesta ordem (re/message_server.md §4.1). O 544 do Channel
    (`SaveOption`) envia o mesmo bloco de 37 bytes.

    Nomes em snake_case, como em docs/architecture/07-progression.md §4.6. `mouse_sensitivity` é
    `mousesence` no RE. A ordem dos campos é o layout: não reordenar."""

    background: int = 0
    effect: int = 0
    voice_info: int = 0
    voice_character: int = 0
    mouse_acc: int = 0
    mouse_sensitivity: int = 0
    mouse_invert: int = 0
    weapon_1: int = 0
    weapon_2: int = 0
    weapon_3: int = 0
    weapon_4: int = 0
    weapon_5: int = 0
    weapon_6: int = 0
    weapon_7: int = 0
    weapon_8: int = 0
    weapon_9: int = 0
    weapon_0: int = 0
    move_forward: int = 0
    move_backward: int = 0
    move_left: int = 0
    move_right: int = 0
    fire: int = 0
    alt_fire: int = 0
    walk: int = 0
    down: int = 0
    jump: int = 0
    change_mag: int = 0
    chaff: int = 0
    booster: int = 0
    action: int = 0
    speech_menu_1: int = 0
    speech_menu_2: int = 0
    speech_menu_3: int = 0
    object: int = 0
    mirror: int = 0
    minimap: int = 0
    screenshot: int = 0

    _FIXED = struct.Struct("<37B")

    def pack(self) -> bytes:
        return self._FIXED.pack(*astuple(self))

    @classmethod
    def unpack(cls, payload: bytes) -> LmRegisterInfo:
        """Lê os 37 primeiros bytes. Payload curto levanta `struct.error`, que o roteador loga."""
        return cls(*cls._FIXED.unpack_from(payload))


@dataclass(frozen=True, slots=True)
class MsRegisterOut:
    """MS_REGISTER_OUT (111): LM_REGISTER_INFO @0x00, `char session_key[33]` @0x25 (32 hex + NUL),
    padding @0x46..0x47, result @0x48. Total 0x4C. Layout: re/message_server.md §4."""

    options: LmRegisterInfo = LmRegisterInfo()
    session_key: str = ""
    result: int = 0
    opcode: ClassVar[int] = MsOp.REGISTER_OUT

    _FIXED = struct.Struct("<37s33s2xi")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.options.pack(), cfield(self.session_key, 33), self.result)


@dataclass(frozen=True, slots=True)
class MsInMessageServerOut:
    """MS_IN_MESSAGE_SERVER_OUT (121): i32 result @0, nickname char[17] @4, zeros @0x15..0x17,
    i32 clan_code @0x18. Total 0x1C. Nickname com mais de 16 bytes é truncado."""

    result: int
    nickname: str = ""
    clan_code: int = 0
    opcode: ClassVar[int] = MsOp.IN_MESSAGE_SERVER_OUT

    _FIXED = struct.Struct("<i17s3xi")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.result, cfield(self.nickname, 17), self.clan_code)


@dataclass(frozen=True, slots=True)
class LmServerInfo:
    """LM_SERVER_INFO: entrada de 72 bytes de MS_GET_CHANNEL_SERVER_OUT (§4.2 do RE)."""

    server_id: int
    service_port: int
    max_client_count: int
    server_name: str
    service_address: str
    server_type: int = 0
    server_group: int = 0
    channel_mode: int = 0
    access_level: int = 0
    access_exp: int = 0
    curr_client_count: int = 0
    pick_client_count: int = 0

    _FIXED = struct.Struct("<HBBBB2xiHHHH16s36s")

    def pack(self) -> bytes:
        return self._FIXED.pack(
            self.server_id,
            self.server_type,
            self.server_group,
            self.channel_mode,
            self.access_level,
            self.access_exp,
            self.max_client_count,
            self.curr_client_count,
            self.pick_client_count,
            self.service_port,
            cfield(self.service_address, 16),
            cfield(self.server_name, 36),
        )


@dataclass(frozen=True, slots=True)
class MsGetChannelServerOut:
    """MS_GET_CHANNEL_SERVER_OUT (131): u8 count @0, u8 bRandom @1, count LM_SERVER_INFO @2."""

    channels: tuple[LmServerInfo, ...]
    b_random: bool = False
    opcode: ClassVar[int] = MsOp.GET_CHANNEL_SERVER_OUT

    def pack(self) -> bytes:
        if len(self.channels) > 255:
            raise ValueError(f"canais demais para MS_GET_CHANNEL_SERVER_OUT: {len(self.channels)}")
        head = struct.pack("<BB", len(self.channels), int(self.b_random))
        return head + b"".join(c.pack() for c in self.channels)


# Amigos, bloqueios e sussurro (F12). Layouts: re/protocol_full.md §2.1 e §2.2, e os cases
# 161, 183, 184, 188, 189, 191 e 193 de re/LM_Engine.dll/message_dispatch_FUN_10025120.c.

MAX_WHISPER_TEXT = 0x78  # o cliente descarta sussurro com `len > 0x78` (case 161)
MAX_RELATION_IDS = 14  # ids por pedido de 190 e 192 (máximo do wrapper do cliente)
ONLINE_STATE = 0x22  # estado de amigo conectado; o cliente grava 0x22 ou 0 (case 191)


@dataclass(frozen=True, slots=True)
class MsNickIn:
    """ADD_FRIEND (181) e ADD_BLACK (186): `char nick[17]` @0, NUL-terminado."""

    nickname: str
    _FIXED = struct.Struct("<17s")

    @classmethod
    def unpack(cls, payload: bytes) -> MsNickIn:
        (raw,) = cls._FIXED.unpack_from(payload)  # payload curto: struct.error, logado
        return cls(cstr(raw))

    def pack(self) -> bytes:
        return self._FIXED.pack(cfield(self.nickname, 17))


@dataclass(frozen=True, slots=True)
class MsAccountIdIn:
    """DEL_FRIEND (182) e DEL_BLACK (187): `i32 account_id` @0. O cliente envia o id que recebeu no
    183 ou no 188 (chave do nó). Zero significa que o cliente não achou o nick na lista local."""

    account_id: int
    _FIXED = struct.Struct("<i")

    @classmethod
    def unpack(cls, payload: bytes) -> MsAccountIdIn:
        (account_id,) = cls._FIXED.unpack_from(payload)
        return cls(account_id)

    def pack(self) -> bytes:
        return self._FIXED.pack(self.account_id)


@dataclass(frozen=True, slots=True)
class MsContactRecord:
    """Registro de amigo (183) ou de bloqueado (188): 0x2C bytes.

    @0 `i32` id da conta (chave do nó, eco no 182 e no 187); @4 nick `char[16]` com NUL em @0x14
    (`cfield(nick, 17)`); @0x20 `i32` total_exp; @0x25 estado (0x22 conectado, 0 fora); @0x28
    `i32` result: o cliente só insere com `>= 0`. Clã (@0x18, @0x1c), nest (@0x24) e veículo
    (@0x26) ficam zero.

    shortcut: nest e clã são zero porque a conta ainda não tem nest (`regular_nest_id`) nem clã
    (F13). Recusa usa `result` negativo e id 0 (ver handlers/message/social.py).
    """

    account_id: int
    nickname: str
    total_exp: int = 0
    online: bool = False
    result: int = 0
    _FIXED = struct.Struct("<i17s3xiiiBBBxi")

    def pack(self) -> bytes:
        return self._FIXED.pack(
            self.account_id,
            cfield(self.nickname, 17),
            0,  # siClan @0x18
            0,  # clan_mark @0x1c
            self.total_exp,  # @0x20
            0,  # ucNest @0x24
            ONLINE_STATE if self.online else 0,  # @0x25
            0,  # ucVehicleLicence @0x26
            self.result,  # @0x28
        )


@dataclass(frozen=True, slots=True)
class MsFriendListOut:
    """FRIEND_LIST_OUT (183): um registro por pacote. O cliente insere ou atualiza o nó da chave."""

    record: MsContactRecord
    opcode: ClassVar[int] = MsOp.FRIEND_LIST_OUT

    def pack(self) -> bytes:
        return self.record.pack()


@dataclass(frozen=True, slots=True)
class MsBlackListOut:
    """BLACK_LIST_OUT (188): mesmo registro de 183, um por pacote."""

    record: MsContactRecord
    opcode: ClassVar[int] = MsOp.BLACK_LIST_OUT

    def pack(self) -> bytes:
        return self.record.pack()


@dataclass(frozen=True, slots=True)
class MsDelFriendOut:
    """DEL_FRIEND_OUT (184): `i32 account_id` @0 (chave do nó) e `i32 result` @4. O cliente remove
    o nó só com result 0 (dispatcher, case 184)."""

    account_id: int
    result: int
    opcode: ClassVar[int] = MsOp.DEL_FRIEND_OUT
    _FIXED = struct.Struct("<ii")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.account_id, self.result)


@dataclass(frozen=True, slots=True)
class MsDelBlackOut:
    """DEL_BLACK_OUT (189): mesmo layout de 184. Remove o bloqueado só com result 0."""

    account_id: int
    result: int
    opcode: ClassVar[int] = MsOp.DEL_BLACK_OUT
    _FIXED = struct.Struct("<ii")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.account_id, self.result)


@dataclass(frozen=True, slots=True)
class MsRelationIdsIn:
    """REFRESH_FRIEND (190) e REFRESH_BLACK (192): `u8 count` @0 (1 a 14), padding @1..3, e
    `i32 account_id[count]` a partir de @4."""

    account_ids: tuple[int, ...]

    @classmethod
    def unpack(cls, payload: bytes) -> MsRelationIdsIn:
        (count,) = struct.unpack_from("<B", payload)
        if not 1 <= count <= MAX_RELATION_IDS:
            raise ValueError(f"pedido de relação com {count} ids (máximo {MAX_RELATION_IDS})")
        return cls(struct.unpack_from(f"<{count}i", payload, 4))

    def pack(self) -> bytes:
        return struct.pack("<B3x", len(self.account_ids)) + struct.pack(
            f"<{len(self.account_ids)}i", *self.account_ids
        )


@dataclass(frozen=True, slots=True)
class MsRelationState:
    """Registro de 0x14 bytes de 191 e 193: `i32 account_id` @0 (chave), `i32 total_exp` @4,
    `i32 clan` @8, `i32 clan_mark` @0xc, `u8 nest` @0x10, `u8 estado` @0x11 (0x22 conectado)."""

    account_id: int
    total_exp: int
    online: bool = False
    _FIXED = struct.Struct("<iiiiBB2x")

    def pack(self) -> bytes:
        state = ONLINE_STATE if self.online else 0
        return self._FIXED.pack(self.account_id, self.total_exp, 0, 0, 0, state)


@dataclass(frozen=True, slots=True)
class MsRefreshFriendOut:
    """REFRESH_FRIEND_OUT (191): `u8 count` @0, padding @1..3, registros de 0x14 a partir de @4.
    O cliente só atualiza nós que já tem; lote vazio é válido."""

    records: tuple[MsRelationState, ...]
    opcode: ClassVar[int] = MsOp.REFRESH_FRIEND_OUT
    _HEAD = struct.Struct("<B3x")

    def pack(self) -> bytes:
        return self._HEAD.pack(len(self.records)) + b"".join(r.pack() for r in self.records)


@dataclass(frozen=True, slots=True)
class MsRefreshBlackOut:
    """REFRESH_BLACK_OUT (193): mesmo lote de 191, para bloqueados."""

    records: tuple[MsRelationState, ...]
    opcode: ClassVar[int] = MsOp.REFRESH_BLACK_OUT
    _HEAD = struct.Struct("<B3x")

    def pack(self) -> bytes:
        return self._HEAD.pack(len(self.records)) + b"".join(r.pack() for r in self.records)


@dataclass(frozen=True, slots=True)
class MsSendWhisperIn:
    """SEND_WHISPER (160): `char target[18]` @0 (NUL), `u16 len` @0x12, texto `len` bytes @0x14."""

    target: str
    text: bytes
    _HEAD = struct.Struct("<18sH")

    @classmethod
    def unpack(cls, payload: bytes) -> MsSendWhisperIn:
        raw_target, length = cls._HEAD.unpack_from(payload)  # payload curto: struct.error
        end = cls._HEAD.size + length
        if length > MAX_WHISPER_TEXT or len(payload) < end:
            raise ValueError(f"MS_SEND_WHISPER_IN inconsistente: len={length}")
        return cls(cstr(raw_target), payload[cls._HEAD.size : end])

    def pack(self) -> bytes:
        return self._HEAD.pack(cfield(self.target, 18), len(self.text)) + self.text


@dataclass(frozen=True, slots=True)
class MsWhisperOut:
    """SEND_WHISPER_OUT (161), ao destinatário: `char sender[18]` @0, `u16 len` @0x12, texto @0x14.
    Sem NUL no fim: o cliente grava o terminador após `len` bytes."""

    sender: str
    text: bytes
    opcode: ClassVar[int] = MsOp.SEND_WHISPER_OUT
    _HEAD = struct.Struct("<18sH")

    def pack(self) -> bytes:
        return self._HEAD.pack(cfield(self.sender, 18), len(self.text)) + self.text


@dataclass(frozen=True, slots=True)
class MsWhisperErrorOut:
    """SEND_WHISPER_ERROR_OUT (162), ao remetente: `i32 result` @0, `char receiver[18]` @4,
    `u16 len` @0x16, texto @0x18. O cliente mostra o texto fixo "falhou ao receber a mensagem"."""

    result: int
    receiver: str
    text: bytes
    opcode: ClassVar[int] = MsOp.SEND_WHISPER_ERROR_OUT
    _HEAD = struct.Struct("<i18sH")

    def pack(self) -> bytes:
        head = self._HEAD.pack(self.result, cfield(self.receiver, 18), len(self.text))
        return head + self.text
