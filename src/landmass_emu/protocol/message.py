"""Mensagens do Message Server (porta 7313). Layouts em re/NOTES.md e re/message_server.md."""

import struct
from dataclasses import dataclass
from enum import IntEnum

ENCODING = "cp1252"


class MsOp(IntEnum):
    HEARTBEAT = 2
    LOGIN = 100
    REGISTER = 110
    IN_MESSAGE_SERVER = 120
    GET_CHANNEL_SERVER_INFO = 130
    CREATE_NICKNAME = 150


def _cstr(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode(ENCODING, errors="replace")


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
