"""Opcode 130 GetChannelServerInfo: lista de canais da configuração."""

import logging
from collections.abc import Sequence

from landmass_emu.domain.channel import Channel
from landmass_emu.net.server import Reply
from landmass_emu.net.session import Session
from landmass_emu.protocol.message import LmServerInfo, MsGetChannelServerOut

log = logging.getLogger(__name__)


async def get_channel_server_info(
    channels: Sequence[Channel], session: Session, payload: bytes
) -> Sequence[Reply]:
    if session.account is None:
        log.warning("[%s] GetChannelServerInfo antes do login; ignorado", session.peer)
        return []
    entries = tuple(
        LmServerInfo(
            server_id=c.server_id,
            service_port=c.port,
            max_client_count=c.max_clients,
            server_name=c.name,
            service_address=c.address,
        )
        for c in channels
    )
    return [MsGetChannelServerOut(entries)]
