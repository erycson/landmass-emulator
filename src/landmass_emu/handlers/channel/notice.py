"""Aviso de texto a todo o lobby do canal (251). Usado pelo desligamento (D202) e pelos comandos de
GM com aviso global: quem chama passa um `str` e não precisa conhecer o layout.
"""

import logging

from landmass_emu.domain.lobby import Lobby
from landmass_emu.net.server import reply_body
from landmass_emu.protocol.header import CHANNEL_NET_CODE
from landmass_emu.protocol.notice import MAX_NOTICE_BYTES, CsSendCommandOut

log = logging.getLogger(__name__)


class GlobalNotice:
    def __init__(self, lobby: Lobby) -> None:
        self._lobby = lobby

    def send(self, text: str) -> None:
        """Manda `text` a quem está no lobby. Caracter fora do cp1252 vira `?`. Texto que passa do
        limite do cliente é cortado, com aviso no log; texto vazio é erro de quem chama."""
        raw = text.encode("cp1252", errors="replace")
        if not raw:
            raise ValueError("aviso vazio")
        if len(raw) > MAX_NOTICE_BYTES:
            log.warning("aviso cortado de %d para %d bytes", len(raw), MAX_NOTICE_BYTES)
            raw = raw[:MAX_NOTICE_BYTES]
        self._lobby.broadcast(reply_body(CsSendCommandOut(raw), CHANNEL_NET_CODE))
