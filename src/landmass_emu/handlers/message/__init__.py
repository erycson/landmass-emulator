"""Roteador do Message Server: tabela explícita opcode → método, sem descoberta automática."""

from collections.abc import Sequence

from landmass_emu.domain.channel import Channel
from landmass_emu.handlers.message.account import AccountHandlers
from landmass_emu.handlers.message.channel_list import ChannelListHandlers
from landmass_emu.net.server import Reply, Router
from landmass_emu.net.session import Session
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.options import OptionsRepository
from landmass_emu.ports.session_keys import SessionKeyRegistry
from landmass_emu.protocol.message import MsOp


class MessageHandlers:
    """Dependências entram no `__init__`; `router` é a tabela opcode → método."""

    def __init__(
        self,
        accounts: AccountRepository,
        channels: Sequence[Channel],
        sessions: SessionKeyRegistry,
        options: OptionsRepository,
    ) -> None:
        self._account = AccountHandlers(accounts, sessions, options)
        self._channel_list = ChannelListHandlers(channels)
        self.router: Router = {
            MsOp.HEARTBEAT: self.heartbeat,
            MsOp.LOGIN: self._account.login,
            MsOp.REGISTER: self._account.register,
            MsOp.IN_MESSAGE_SERVER: self._account.in_message_server,
            MsOp.GET_CHANNEL_SERVER_INFO: self._channel_list.get_channel_server_info,
        }

    async def heartbeat(self, session: Session, payload: bytes) -> Sequence[Reply]:
        return []
