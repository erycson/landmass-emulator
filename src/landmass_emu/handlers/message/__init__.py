"""Roteador do Message Server: tabela explícita opcode → handler, sem descoberta automática."""

from collections.abc import Sequence
from functools import partial

from landmass_emu.domain.channel import Channel
from landmass_emu.handlers.message import account, channel_list
from landmass_emu.net.server import Reply, Router
from landmass_emu.net.session import Session
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.options import OptionsRepository
from landmass_emu.ports.session_keys import SessionKeyRegistry
from landmass_emu.protocol.message import MsOp


async def _heartbeat(session: Session, payload: bytes) -> Sequence[Reply]:
    return []


def build_router(
    accounts: AccountRepository,
    channels: Sequence[Channel],
    sessions: SessionKeyRegistry,
    options: OptionsRepository,
) -> Router:
    return {
        MsOp.HEARTBEAT: _heartbeat,
        MsOp.LOGIN: partial(account.login, accounts),
        MsOp.REGISTER: partial(account.register, sessions, options),
        MsOp.IN_MESSAGE_SERVER: account.in_message_server,
        MsOp.GET_CHANNEL_SERVER_INFO: partial(channel_list.get_channel_server_info, channels),
    }
