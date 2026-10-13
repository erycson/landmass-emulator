"""Roteador do Channel Server: tabela explícita opcode → handler, sem descoberta automática."""

from collections.abc import Callable, Sequence
from functools import partial

from landmass_emu.domain.lobby import Lobby
from landmass_emu.handlers.channel import chat, entry, options
from landmass_emu.net.server import Reply, Router
from landmass_emu.net.session import Session
from landmass_emu.ports.options import OptionsRepository
from landmass_emu.ports.session_keys import SessionKeyRegistry
from landmass_emu.protocol.channel import CsOp


async def _heartbeat(session: Session, payload: bytes) -> Sequence[Reply]:
    # O cliente responde com 2 ao heartbeat do servidor. Não respondemos: o eco faria um laço.
    # shortcut: o servidor manda 2 a cada 10 s; se o cliente real cair por time_out (20 s) com
    # esse intervalo, reduzir o intervalo em app.py (CHANNEL_HEARTBEAT_SECONDS).
    return []


def build_router(
    sessions: SessionKeyRegistry, lobby: Lobby, player_options: OptionsRepository
) -> Router:
    return {
        CsOp.HEARTBEAT: _heartbeat,
        CsOp.IN_CHANNEL_SERVER: partial(entry.in_channel_server, sessions),
        CsOp.IN_CHANNEL: partial(entry.in_channel, lobby),
        CsOp.OUT_CHANNEL: partial(entry.out_channel, lobby),
        CsOp.SEND_MESSAGE: partial(chat.send_message, lobby),
        CsOp.SAVE_OPTION: partial(options.save_option, player_options),
    }


def disconnect_handler(lobby: Lobby) -> Callable[[Session], None]:
    return partial(entry.disconnect, lobby)
