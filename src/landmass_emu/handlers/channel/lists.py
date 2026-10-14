"""Listas sob pedido: 464 (lista do lobby, resposta 151), 542 (ficha do jogador, resposta 543),
546 (jogadores, resposta 548) e 545 (salas, resposta 547).

Só responde a quem está no lobby. Pedido sem nenhum item conhecido não gera resposta.
"""

from collections.abc import Sequence

from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.rooms import Rooms
from landmass_emu.handlers.channel.records import ChannelRecords
from landmass_emu.net.server import Reply
from landmass_emu.net.session import Session
from landmass_emu.ports.profile import PlayerProfileRepository
from landmass_emu.protocol.channel import (
    MAX_LOBBY_ENTRIES,
    CsChannelPlayerInfoOut,
    CsErrorEnvelope,
    CsOp,
    CsPlayerDetailIn,
    CsPlayerDetailOut,
    CsPlayerProperty,
    CsRefreshPlayerListIn,
    CsRefreshPlayerListOut,
    CsRefreshRoomListIn,
    CsRefreshRoomListOut,
)

# shortcut: código do envelope 54 do 543 quando o nick não está no canal (CERR_FIND_PLAYER,
# `tools/re/layouts_f0.md` §7.3). A UI deve fechar "Buscando..."; a mensagem não é conhecida.
# Confirmar.
ERR_FIND_PLAYER = -2460


class ListHandlers:
    def __init__(
        self,
        lobby: Lobby,
        rooms: Rooms,
        records: ChannelRecords,
        profiles: PlayerProfileRepository,
    ) -> None:
        self._lobby = lobby
        self._rooms = rooms
        self._records = records
        self._profiles = profiles

    async def channel_player_info(self, session: Session, payload: bytes) -> Sequence[Reply]:
        """464, sem corpo: a lista do lobby (151). Quem está numa sala não recebe: o 151 põe
        `+0xb0 = 0x22` em todo nó da lista, o do próprio pedido também (`LM_Engine` case 0x97,
        L1223-1225), e isso tira a posição 0x23 que `ChangeTeam` exige."""
        guid = self._lobby.guid_of(session)
        if guid is None or self._rooms.room_of(guid) is not None:
            return []
        return [CsChannelPlayerInfoOut(self._records.lobby_players()[:MAX_LOBBY_ENTRIES])]

    async def player_detail(self, session: Session, payload: bytes) -> Sequence[Reply]:
        """542: ficha do jogador do clique no nick, com os dados do banco (D107). Nick fora do
        canal, ou conta sem ficha: envelope 54 com o código."""
        if self._lobby.guid_of(session) is None:
            return []
        req = CsPlayerDetailIn.unpack(payload)
        guid = self._lobby.guid_of_nick(req.nickname)
        profile = None if guid is None else await self._profiles.profile(guid)
        if profile is None:
            return [CsErrorEnvelope(CsOp.PLAYER_DETAIL_OUT, ERR_FIND_PLAYER)]
        return [
            CsPlayerDetailOut(
                nickname=req.nickname,
                rank=profile.rank,
                games=profile.games,
                wins=profile.wins,
                losses=profile.losses,
                kills=profile.kills,
                deaths=profile.deaths,
                headshots=profile.headshots,
                total_exp=profile.total_exp,
                nest=profile.nest,
                clan_mark=profile.clan_mark,
                clan=profile.clan_name,
            )
        ]

    async def refresh_player_list(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if self._lobby.guid_of(session) is None:
            return []
        req = CsRefreshPlayerListIn.unpack(payload)
        # shortcut: clã e nest saem zerados (o lobby guarda só nick e exp).
        found = tuple(
            CsPlayerProperty(client_guid=g, total_exp=self._lobby.exp_of(g))
            for g in req.client_guids
            if self._lobby.is_member(g)
        )
        if not found:
            return []
        return [CsRefreshPlayerListOut(found)]

    async def refresh_room_list(self, session: Session, payload: bytes) -> Sequence[Reply]:
        if self._lobby.guid_of(session) is None:
            return []
        req = CsRefreshRoomListIn.unpack(payload)
        rooms = (self._rooms.get(g) for g in req.room_guids)
        found = tuple(self._records.room(r) for r in rooms if r is not None)
        if not found:
            return []
        return [CsRefreshRoomListOut(found)]
