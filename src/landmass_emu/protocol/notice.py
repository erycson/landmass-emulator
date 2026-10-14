"""Aviso geral do canal (251, `NotifySendCommand`): o cliente mostra o texto no chat e no HUD, sem
remetente. Layout em `tools/re/LM_Engine.dll/all/10004310_NotifySendCommand.c`: `u8 len` @0 e
texto[len]
@1, lido como cp1252 (`MultiByteToWideChar` com a página de código do sistema). O buffer do cliente
comporta 120 bytes, o mesmo limite do chat (`MAX_CHAT_TEXT`). O codificador é o `CsSendCommandOut`
do canal, o mesmo dos comandos de GM (D193); o NUL que ele acrescenta fica fora do `len`.

O 241 não serve: o cliente procura o remetente pelo guid e descarta a mensagem quando não acha.
"""

from landmass_emu.protocol.channel import MAX_CHAT_TEXT, CsOp, CsSendCommandOut

NOTICE_OPCODE = CsOp.SEND_COMMAND_OUT
MAX_NOTICE_BYTES = MAX_CHAT_TEXT

__all__ = ["MAX_NOTICE_BYTES", "NOTICE_OPCODE", "CsSendCommandOut"]
