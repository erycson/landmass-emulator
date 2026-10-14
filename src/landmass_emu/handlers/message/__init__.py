"""Roteador do Message Server: tabela explícita opcode → método, sem descoberta automática."""

from collections.abc import Sequence

from landmass_emu.domain.channel import Channel
from landmass_emu.domain.presence import MessagePresence
from landmass_emu.handlers.message.account import AccountHandlers
from landmass_emu.handlers.message.channel_list import ChannelListHandlers
from landmass_emu.handlers.message.clan import ClanHandlers
from landmass_emu.handlers.message.ranking import RankingHandlers
from landmass_emu.handlers.message.social import SocialHandlers
from landmass_emu.handlers.message.whisper import WhisperHandlers
from landmass_emu.net.server import Reply, Router
from landmass_emu.net.session import Session
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.clans import ClanRepository
from landmass_emu.ports.options import OptionsRepository
from landmass_emu.ports.ranking import RankingRepository
from landmass_emu.ports.session_keys import SessionKeyRegistry
from landmass_emu.ports.social import SocialRepository
from landmass_emu.protocol.message import MsOp


class MessageHandlers:
    """Dependências entram no `__init__`; `router` é a tabela opcode → método."""

    def __init__(
        self,
        accounts: AccountRepository,
        channels: Sequence[Channel],
        sessions: SessionKeyRegistry,
        options: OptionsRepository,
        social: SocialRepository,
        presence: MessagePresence,
        clans: ClanRepository,
        ranking: RankingRepository,
    ) -> None:
        self._account = AccountHandlers(accounts, sessions, options, presence, clans)
        self._channel_list = ChannelListHandlers(channels)
        self._social = SocialHandlers(accounts, social, presence)
        self._whisper = WhisperHandlers(accounts, social, presence)
        self._clan = ClanHandlers(clans, presence)
        self._ranking = RankingHandlers(ranking)
        self.router: Router = {
            MsOp.GET_RANKING: self._ranking.get_ranking,
            MsOp.GET_CLAN_INFO: self._clan.get_clan_info,
            MsOp.GET_CLAN_MEMBER: self._clan.get_clan_member,
            MsOp.SEND_CLAN_MESSAGE: self._clan.send_clan_message,
            MsOp.REFRESH_CLAN: self._clan.refresh_clan,
            MsOp.HEARTBEAT: self.heartbeat,
            MsOp.LOGIN: self._account.login,
            MsOp.REGISTER: self._account.register,
            MsOp.IN_MESSAGE_SERVER: self._account.in_message_server,
            MsOp.GET_CHANNEL_SERVER_INFO: self._channel_list.get_channel_server_info,
            MsOp.SEND_WHISPER: self._whisper.send_whisper,
            MsOp.GET_FRIEND_LIST: self._social.get_friend_list,
            MsOp.ADD_FRIEND: self._social.add_friend,
            MsOp.DEL_FRIEND: self._social.del_friend,
            MsOp.ADD_BLACK: self._social.add_block,
            MsOp.DEL_BLACK: self._social.del_block,
            MsOp.REFRESH_FRIEND: self._social.refresh_friends,
            MsOp.REFRESH_BLACK: self._social.refresh_blocks,
        }

    async def heartbeat(self, session: Session, payload: bytes) -> Sequence[Reply]:
        return []
