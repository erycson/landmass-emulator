"""Aviso geral do canal (251, `NotifySendCommand`): o cliente mostra o texto no chat e no HUD, sem
remetente. Layout em `re/LM_Engine.dll/all/10004310_NotifySendCommand.c`: `u8 len` @0 e texto[len]
@1, lido como cp1252 (`MultiByteToWideChar` com a página de código do sistema). O buffer do cliente
comporta 120 bytes sem NUL, o mesmo limite do chat (`MAX_CHAT_TEXT`).

O 241 não serve: o cliente procura o remetente pelo guid e descarta a mensagem quando não acha.
"""

import struct
from dataclasses import dataclass
from typing import ClassVar

from landmass_emu.protocol.channel import MAX_CHAT_TEXT

NOTICE_OPCODE = 251
MAX_NOTICE_BYTES = MAX_CHAT_TEXT


@dataclass(frozen=True, slots=True)
class CsSendCommandOut:
    """SEND_COMMAND_OUT (251): `u8 len` @0, texto[len] @1, em cp1252 e sem NUL final."""

    text: bytes
    opcode: ClassVar[int] = NOTICE_OPCODE
    _HEAD = struct.Struct("<B")

    def pack(self) -> bytes:
        if not 0 < len(self.text) <= MAX_NOTICE_BYTES:
            raise ValueError(
                f"aviso de {len(self.text)} bytes; o cliente aceita de 1 a {MAX_NOTICE_BYTES}"
            )
        return self._HEAD.pack(len(self.text)) + self.text
