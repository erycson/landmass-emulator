"""Opções do jogador: 544 SaveOption grava as 37 opções da conta logada. Sem resposta conhecida."""

import logging
from collections.abc import Sequence

from landmass_emu.net.server import Reply
from landmass_emu.net.session import Session
from landmass_emu.ports.options import OptionsRepository
from landmass_emu.protocol.message import LmRegisterInfo

log = logging.getLogger(__name__)


async def save_option(
    options: OptionsRepository, session: Session, payload: bytes
) -> Sequence[Reply]:
    if session.account is None:
        log.warning("[%s] SaveOption antes do login; ignorado", session.peer)
        return []
    # Payload curto levanta struct.error; o roteador loga e ignora, sem gravar.
    await options.save(session.account.id, LmRegisterInfo.unpack(payload))
    return []
