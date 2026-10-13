"""Channel Server: monta os handlers por assunto e a tabela explícita opcode → método."""

from collections.abc import Sequence

from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.rooms import Rooms
from landmass_emu.handlers.channel.chat import ChatHandlers
from landmass_emu.handlers.channel.entry import EntryHandlers
from landmass_emu.handlers.channel.lists import ListHandlers
from landmass_emu.handlers.channel.options import OptionHandlers
from landmass_emu.handlers.channel.records import ChannelRecords
from landmass_emu.handlers.channel.rooms import GameEndpoint, RoomHandlers
from landmass_emu.net.server import Reply, Router
from landmass_emu.net.session import Session
from landmass_emu.ports.options import OptionsRepository
from landmass_emu.ports.session_keys import SessionKeyRegistry
from landmass_emu.protocol.channel import CsOp


class ChannelHandlers:
    """Dependências entram no `__init__`; `router` é a tabela opcode → método."""

    def __init__(
        self,
        sessions: SessionKeyRegistry,
        lobby: Lobby,
        rooms: Rooms,
        player_options: OptionsRepository,
        game: GameEndpoint,
    ) -> None:
        records = ChannelRecords(lobby)
        room_handlers = RoomHandlers(lobby, rooms, records, game)
        self._entry = EntryHandlers(sessions, lobby, rooms, records, room_handlers)
        self._chat = ChatHandlers(lobby, rooms)
        self._lists = ListHandlers(lobby, rooms, records)
        self._options = OptionHandlers(player_options)
        self._rooms = room_handlers
        self.router: Router = {
            CsOp.HEARTBEAT: self.heartbeat,
            CsOp.IN_CHANNEL_SERVER: self._entry.in_channel_server,
            CsOp.IN_CHANNEL: self._entry.in_channel,
            CsOp.OUT_CHANNEL: self._entry.out_channel,
            CsOp.SEND_MESSAGE: self._chat.send_message,
            CsOp.SAVE_OPTION: self._options.save_option,
            CsOp.CREATE_ROOM: self._rooms.create_room,
            CsOp.IN_ROOM: self._rooms.in_room,
            CsOp.OUT_ROOM: self._rooms.out_room,
            CsOp.READY_GAME: self._rooms.ready_game,
            CsOp.CHANGE_ROOM_SLOT: self._rooms.change_room_slot,
            CsOp.EXPEL_PLAYER: self._rooms.expel_player,
            CsOp.REFRESH_PLAYER_LIST: self._lists.refresh_player_list,
            CsOp.REFRESH_ROOM_LIST: self._lists.refresh_room_list,
        }

    async def heartbeat(self, session: Session, payload: bytes) -> Sequence[Reply]:
        # O cliente responde com 2 ao heartbeat do servidor. Não respondemos: o eco faria um laço.
        # shortcut: o servidor manda 2 a cada 10 s; se o cliente real cair por time_out (20 s) com
        # esse intervalo, reduzir o intervalo em app.py (CHANNEL_HEARTBEAT_SECONDS).
        return []

    def disconnect(self, session: Session) -> None:
        """Queda da conexão: sai da sala e do lobby, e avisa os demais."""
        self._entry.disconnect(session)
