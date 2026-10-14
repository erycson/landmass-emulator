"""Channel Server: monta os handlers por assunto e a tabela explícita opcode → método."""

from collections.abc import Callable, Sequence

from landmass_emu.audit import EconomyAudit
from landmass_emu.domain.loadout import LoadoutService
from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.progression import ProgressionService
from landmass_emu.domain.regular import RegularService
from landmass_emu.domain.rooms import Rooms
from landmass_emu.domain.shop import ShopService
from landmass_emu.handlers.channel.chat import ChatHandlers
from landmass_emu.handlers.channel.entry import EntryHandlers
from landmass_emu.handlers.channel.equipment import EquipmentHandlers
from landmass_emu.handlers.channel.gift import GiftHandlers
from landmass_emu.handlers.channel.gm import GmHandlers
from landmass_emu.handlers.channel.lists import ListHandlers
from landmass_emu.handlers.channel.login import LoginHandlers
from landmass_emu.handlers.channel.morat import MoratHandlers
from landmass_emu.handlers.channel.options import OptionHandlers
from landmass_emu.handlers.channel.progression import ProgressionHandlers
from landmass_emu.handlers.channel.records import ChannelRecords
from landmass_emu.handlers.channel.rooms import RoomHandlers
from landmass_emu.handlers.channel.shop import ShopHandlers
from landmass_emu.net.server import Handler, Reply, Router
from landmass_emu.net.session import Session
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.inventory import InventoryRepository
from landmass_emu.ports.match_host import MapCatalog, MatchHost
from landmass_emu.ports.matches import MatchRepository
from landmass_emu.ports.options import OptionsRepository
from landmass_emu.ports.profile import PlayerProfileRepository
from landmass_emu.ports.progression import ProgressionRepository
from landmass_emu.ports.session_keys import SessionKeyRegistry
from landmass_emu.protocol.channel import CsOp
from landmass_emu.protocol.gift import CsGiftOp
from landmass_emu.protocol.inventory import CsInventoryOp
from landmass_emu.protocol.progression import CsProgressionOp
from landmass_emu.protocol.shop import CsShopOp


class ChannelHandlers:
    """Dependências entram no `__init__`; `router` é a tabela opcode → método."""

    def __init__(
        self,
        sessions: SessionKeyRegistry,
        lobby: Lobby,
        rooms: Rooms,
        player_options: OptionsRepository,
        progression: ProgressionRepository,
        match: MatchHost,
        maps: MapCatalog,
        matches: MatchRepository | None,
        accounts: AccountRepository,
        inventory: InventoryRepository,
        shop: ShopService,
        equipment: EquipmentHandlers | None = None,
        audit: EconomyAudit | None = None,
        *,
        profiles: PlayerProfileRepository,
        gifts: GiftHandlers | None = None,
        loadout: LoadoutService | None = None,
        accepting_matches: Callable[[], bool] | None = None,
        match_bots: int = 0,
    ) -> None:
        records = ChannelRecords(lobby)
        room_handlers = RoomHandlers(
            lobby,
            rooms,
            records,
            match,
            maps,
            matches,
            progression=progression,
            audit=audit,
            loadout=loadout,
            accepting_matches=accepting_matches,
            match_bots=match_bots,
        )
        progression_handlers = ProgressionHandlers(progression, ProgressionService())
        self._entry = EntryHandlers(
            sessions, lobby, rooms, records, room_handlers, progression_handlers
        )
        self._login = LoginHandlers(self._entry, accounts, inventory)
        self._morats = MoratHandlers(accounts, RegularService())
        self._chat = ChatHandlers(lobby, rooms, match)
        self._gm = GmHandlers(lobby, audit)
        self._lists = ListHandlers(lobby, rooms, records, profiles)
        self._options = OptionHandlers(player_options)
        self._rooms = room_handlers
        self._shop = ShopHandlers(shop, audit)
        routes: dict[int, Handler] = {
            CsShopOp.ITEM_BUY_IN: self._shop.item_buy,
            CsOp.HEARTBEAT: self.heartbeat,
            CsOp.IN_CHANNEL_SERVER: self._login.in_channel_server,
            CsOp.IN_CHANNEL: self._entry.in_channel,
            CsOp.OUT_CHANNEL: self._entry.out_channel,
            CsOp.SEND_MESSAGE: self._chat.send_message,
            CsOp.SEND_COMMAND: self._gm.send_command,
            CsOp.EXPEL_PLAYER: self._gm.expel_player,
            CsOp.SAVE_OPTION: self._options.save_option,
            CsProgressionOp.TUTORIAL_CLEAR: progression_handlers.tutorial_clear,
            CsOp.CREATE_ROOM: self._rooms.create_room,
            CsOp.IN_ROOM: self._rooms.in_room,
            CsOp.ENTER_HANGAR: self._rooms.enter_hangar,
            CsOp.LEAVE_HANGAR: self._rooms.leave_hangar,
            CsOp.OUT_ROOM: self._rooms.out_room,
            CsOp.READY_GAME: self._rooms.ready_game,
            CsOp.EXIT_PLAY: self._rooms.exit_play,
            CsOp.CHANGE_ROOM_PROPERTY: self._rooms.change_room_property,
            CsOp.CHANGE_ROOM_SLOT: self._rooms.change_room_slot,
            CsOp.ROOM_EXPEL: self._rooms.room_expel,
            CsOp.ROOM_INVITE: self._rooms.room_invite,
            CsOp.ROOM_INVITE_ANSWER: self._rooms.room_invite_answer,
            CsOp.GET_CHANNEL_PLAYER_INFO: self._lists.channel_player_info,
            CsOp.PLAYER_DETAIL_IN: self._lists.player_detail,
            CsOp.REFRESH_PLAYER_LIST: self._lists.refresh_player_list,
            CsOp.REFRESH_ROOM_LIST: self._lists.refresh_room_list,
            CsInventoryOp.SET_REGULAR_IN: self._morats.set_regular,
        }
        if equipment is not None:
            routes.update(equipment.router)
        if gifts is not None:
            routes.update(
                {
                    CsGiftOp.GET_GIFT_ITEM_IN: gifts.get_gift_item,
                    CsGiftOp.GIFT_ITEM_USED_IN: gifts.gift_item_used,
                    CsGiftOp.ITEM_GIFT_IN: gifts.item_gift,
                }
            )
        self.router: Router = routes

    async def heartbeat(self, session: Session, payload: bytes) -> Sequence[Reply]:
        # O cliente responde com 2 ao heartbeat do servidor. Não respondemos: o eco faria um laço.
        # shortcut: o servidor manda 2 a cada 10 s; se o cliente real cair por time_out (20 s) com
        # esse intervalo, reduzir o intervalo em app.py (CHANNEL_HEARTBEAT_SECONDS).
        return []

    def disconnect(self, session: Session) -> None:
        """Queda da conexão: sai da sala e do lobby, e avisa os demais."""
        self._entry.disconnect(session)

    async def end_matches(self) -> None:
        """Desligamento: encerra e grava as partidas em andamento (D202)."""
        await self._rooms.end_matches()
