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


class MsResult(IntEnum):
    OK = 0
    INVALID_PASSWORD = -160


def _cstr(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode(ENCODING, errors="replace")


def _cfield(text: str, size: int) -> bytes:
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
            login_num=_cstr(guid),
            user_id=_cstr(payload[off : off + id_len]),
            password=_cstr(payload[off + id_len : off + id_len + pw_len]),
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
    """LM_REGISTER_INFO: 37 bytes u8, nesta ordem (re/message_server.md §4.1)."""

    background: int = 0
    effect: int = 0
    voiceinfo: int = 0
    voicecharacter: int = 0
    mouseacc: int = 0
    mousesence: int = 0
    mouseinvert: int = 0
    weapon1: int = 0
    weapon2: int = 0
    weapon3: int = 0
    weapon4: int = 0
    weapon5: int = 0
    weapon6: int = 0
    weapon7: int = 0
    weapon8: int = 0
    weapon9: int = 0
    weapon0: int = 0
    moveforward: int = 0
    movebackward: int = 0
    moveleft: int = 0
    moveright: int = 0
    fire: int = 0
    altfire: int = 0
    walk: int = 0
    down: int = 0
    jump: int = 0
    changemag: int = 0
    chaff: int = 0
    booster: int = 0
    action: int = 0
    speechmenu1: int = 0
    speechmenu2: int = 0
    speechmenu3: int = 0
    object: int = 0
    mirror: int = 0
    minimap: int = 0
    screenshot: int = 0

    _FIXED = struct.Struct("<37B")

    def pack(self) -> bytes:
        return self._FIXED.pack(*astuple(self))


@dataclass(frozen=True, slots=True)
class MsRegisterOut:
    """MS_REGISTER_OUT (111): LM_REGISTER_INFO @0x00, zeros @0x25..0x45, result @0x48."""

    options: LmRegisterInfo = LmRegisterInfo()
    result: int = 0
    opcode: ClassVar[int] = MsOp.REGISTER_OUT

    _FIXED = struct.Struct("<37s33x2xi")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.options.pack(), self.result)


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
        return self._FIXED.pack(self.result, _cfield(self.nickname, 17), self.clan_code)


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
            _cfield(self.service_address, 16),
            _cfield(self.server_name, 36),
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
