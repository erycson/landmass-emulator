"""Salas do Channel Server em memória: criar, entrar, sair, slots, pronto, início e expulsão.

Só regras, sem bytes nem sessões: o handler (`handlers/channel/rooms.py`) traduz `RoomError` em
código de erro e monta as mensagens. Acessado só pelo loop de eventos, como o lobby (D12).
"""

from dataclasses import dataclass, field
from enum import Enum

# Valores de RS_WAITING e RS_PLAYING em Core.u (constantes UConst " \t0" e " \t1"). O cliente
# compara `state` com elas (ex.: RefreshPlayers, ChangeTeam); 1 é jogando, não espera.
ROOM_WAITING = 0
ROOM_PLAYING = 1
MAX_SLOTS = 70
NAME_MIN_BYTES = 3
# 301 traz char[51] e char[13] (re/layouts_f0.md §7.1).
NAME_MAX_BYTES = 50
PASSWORD_MAX_BYTES = 12
# Campos que o dono muda por 411 (`configure`).
SETTING_FIELDS = frozenset(
    {"map_num", "game_mode", "team_count", "max_player", "limit_time", "limit_score"}
)


class RoomReason(Enum):
    NOT_FOUND = "sala não existe"
    STARTED = "partida já iniciada"
    WRONG_PASSWORD = "senha inválida"
    FULL = "sala cheia"
    ALREADY_IN_ROOM = "já está em uma sala"
    NOT_IN_ROOM = "não está em sala"
    NOT_OWNER = "não é o dono da sala"
    NOT_READY = "ninguém pronto para iniciar"
    NO_TEAM_SLOT = "sem vaga no grupo"
    NO_SUCH_PLAYER = "jogador não está na sala"
    BAD_NAME = "nome fora de 3..50 bytes"
    BAD_PASSWORD = "senha longa demais"
    BAD_SETTING = "configuração inválida para a sala"
    NOT_INVITED = "sem convite pendente para esta sala"


class RoomError(Exception):
    def __init__(self, reason: RoomReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


@dataclass(slots=True)
class RoomMember:
    slot: int
    ready: bool = False
    morats: int = 0


@dataclass(slots=True)
class Room:
    room_id: int
    name: str
    password: str
    scale: int
    game_mode: int
    map_num: int
    max_player: int
    team_count: int
    limit_time: int
    limit_score: int
    master: int
    state: int = ROOM_WAITING
    # Ordem de entrada: é a ordem em que o dono passa a ser outro jogador ao sair.
    members: dict[int, RoomMember] = field(default_factory=dict)
    # Quem ainda não mandou ExitPlay (500) nesta partida. Sala jogando sem ninguém aqui = acabou.
    in_game: set[int] = field(default_factory=set)

    def match_over(self) -> bool:
        return self.state == ROOM_PLAYING and not self.in_game

    def free_slot(self) -> int | None:
        taken = {m.slot for m in self.members.values()}
        return next((i for i in range(self.max_player) if i not in taken), None)

    def slot_guids(self) -> tuple[int, ...]:
        slots = [-1] * MAX_SLOTS
        for guid, member in self.members.items():
            slots[member.slot] = guid
        return tuple(slots)


@dataclass(frozen=True, slots=True)
class LeaveResult:
    room: Room
    removed: bool
    new_master: int | None


@dataclass(frozen=True, slots=True)
class Expelled:
    room: Room
    guid: int


class Rooms:
    """Registro das salas e da sala em que cada jogador está (uma no máximo por jogador)."""

    def __init__(self) -> None:
        self._rooms: dict[int, Room] = {}
        self._room_of: dict[int, int] = {}
        # convidado -> sala do convite pendente.
        # shortcut: sem expiração; o convite fica até a resposta (471). Revisar com captura.
        self._invites: dict[int, int] = {}
        self._last_id = 0

    def all(self) -> list[Room]:
        return [self._rooms[k] for k in sorted(self._rooms)]

    def get(self, room_id: int) -> Room | None:
        return self._rooms.get(room_id)

    def room_of(self, guid: int) -> Room | None:
        room_id = self._room_of.get(guid)
        return None if room_id is None else self._rooms[room_id]

    def create(
        self,
        owner: int,
        *,
        name: str,
        password: str,
        scale: int,
        game_mode: int,
        map_num: int,
        max_player: int,
        team_count: int,
        limit_time: int,
        limit_score: int,
    ) -> Room:
        if self.room_of(owner) is not None:
            raise RoomError(RoomReason.ALREADY_IN_ROOM)
        if not NAME_MIN_BYTES <= len(name.encode("cp1252", errors="replace")) <= NAME_MAX_BYTES:
            raise RoomError(RoomReason.BAD_NAME)
        if len(password.encode("cp1252", errors="replace")) > PASSWORD_MAX_BYTES:
            raise RoomError(RoomReason.BAD_PASSWORD)
        self._last_id += 1
        room = Room(
            room_id=self._last_id,
            name=name,
            password=password,
            scale=scale,
            game_mode=game_mode,
            map_num=map_num,
            max_player=max_player,
            team_count=team_count,
            limit_time=limit_time,
            limit_score=limit_score,
            master=owner,
        )
        # Dono sem pronto na espera: Config (411) e Mudar grupo (420) exigem não pronto (D77).
        room.members[owner] = RoomMember(slot=0)
        self._rooms[room.room_id] = room
        self._room_of[owner] = room.room_id
        return room

    def join(self, room_id: int, guid: int, password: str) -> Room:
        return self._enter(room_id, guid, password)

    def invite(self, owner: int, target: int) -> Room:
        """Convite do dono (461): fica pendente para `target` até a resposta (471)."""
        room = self.room_of(owner)
        if room is None:
            raise RoomError(RoomReason.NOT_IN_ROOM)
        if room.master != owner:
            raise RoomError(RoomReason.NOT_OWNER)
        if room.state != ROOM_WAITING:
            raise RoomError(RoomReason.STARTED)
        if self.room_of(target) is not None:
            raise RoomError(RoomReason.ALREADY_IN_ROOM)
        if len(room.members) >= room.max_player:
            raise RoomError(RoomReason.FULL)
        self._invites[target] = room.room_id
        return room

    def accept_invite(self, guid: int, room_id: int) -> Room:
        """Aceite (471 com aceite): entra sem senha, mas só com convite pendente para esta sala."""
        if self._invites.pop(guid, None) != room_id:
            raise RoomError(RoomReason.NOT_INVITED)
        return self._enter(room_id, guid, None)

    def decline_invite(self, guid: int) -> None:
        self._invites.pop(guid, None)

    def _enter(self, room_id: int, guid: int, password: str | None) -> Room:
        """Põe `guid` no primeiro slot livre. `password` None pula a conferência (convite)."""
        if self.room_of(guid) is not None:
            raise RoomError(RoomReason.ALREADY_IN_ROOM)
        room = self._rooms.get(room_id)
        if room is None:
            raise RoomError(RoomReason.NOT_FOUND)
        if room.state != ROOM_WAITING:
            raise RoomError(RoomReason.STARTED)
        if password is not None and room.password and room.password != password:
            raise RoomError(RoomReason.WRONG_PASSWORD)
        slot = room.free_slot()
        if slot is None or len(room.members) >= room.max_player:
            raise RoomError(RoomReason.FULL)
        room.members[guid] = RoomMember(slot=slot)
        self._room_of[guid] = room_id
        return room

    def leave(self, guid: int) -> LeaveResult | None:
        """Tira o jogador da sala. Sala vazia é removida; se o dono saiu, o próximo assume."""
        room = self.room_of(guid)
        if room is None:
            return None
        del room.members[guid]
        del self._room_of[guid]
        room.in_game.discard(guid)
        if not room.members:
            del self._rooms[room.room_id]
            return LeaveResult(room, removed=True, new_master=None)
        if room.master != guid:
            return LeaveResult(room, removed=False, new_master=None)
        room.master = next(iter(room.members))
        if room.state == ROOM_WAITING:
            room.members[room.master].ready = False  # novo dono sem pronto na espera (D77)
        return LeaveResult(room, removed=False, new_master=room.master)

    def change_slot(self, guid: int, team: int) -> Room:
        """Mudar grupo (420). O cliente manda o grupo novo, não o slot: o grupo do slot `i` é
        `i % team_count` (`ChangeTeam`, `re/rooms.md` §4). Vai para o primeiro slot livre desse
        grupo, sem contar o próprio slot; sem vaga, recusa."""
        room = self.room_of(guid)
        if room is None:
            raise RoomError(RoomReason.NOT_IN_ROOM)
        if room.state != ROOM_WAITING:
            raise RoomError(RoomReason.STARTED)
        grupos = max(room.team_count, 1)
        ocupados = {m.slot for g, m in room.members.items() if g != guid}
        slot = next(
            (s for s in range(room.max_player) if s % grupos == team and s not in ocupados),
            None,
        )
        if slot is None:
            raise RoomError(RoomReason.NO_TEAM_SLOT)
        room.members[guid].slot = slot
        return room

    def toggle_ready(self, guid: int, morats: int) -> tuple[Room, bool]:
        """Pronto de quem não é dono. O dono usa `start`."""
        room = self.room_of(guid)
        if room is None:
            raise RoomError(RoomReason.NOT_IN_ROOM)
        if room.state != ROOM_WAITING:
            raise RoomError(RoomReason.STARTED)
        member = room.members[guid]
        member.ready = not member.ready
        member.morats = morats
        return room, member.ready

    def start(self, owner: int, morats: int) -> Room:
        """O dono inicia quando há ao menos um outro jogador e todos os outros estão prontos."""
        room = self.room_of(owner)
        if room is None:
            raise RoomError(RoomReason.NOT_IN_ROOM)
        if room.master != owner:
            raise RoomError(RoomReason.NOT_OWNER)
        if room.state != ROOM_WAITING:
            raise RoomError(RoomReason.STARTED)
        others = [m for guid, m in room.members.items() if guid != owner]
        if not others or not all(m.ready for m in others):
            raise RoomError(RoomReason.NOT_READY)
        room.members[owner].morats = morats
        room.members[owner].ready = True  # o cliente exige pronto do dono para entrar (D77)
        room.state = ROOM_PLAYING
        room.in_game = set(room.members)
        return room

    def exit_play(self, guid: int) -> Room | None:
        """500: o jogador deixou a partida. Continua na sala. None se não estiver em sala."""
        room = self.room_of(guid)
        if room is not None:
            room.in_game.discard(guid)
        return room

    def finish(self, room_id: int) -> Room | None:
        """Partida acabou: a sala volta à espera e todos perdem o pronto, o dono também (D77)."""
        room = self._rooms.get(room_id)
        if room is None or room.state != ROOM_PLAYING:
            return room
        room.state = ROOM_WAITING
        room.in_game.clear()
        for member in room.members.values():
            member.ready = False
        return room

    def configure(self, owner: int, changes: dict[str, int]) -> Room:
        """Muda campos da sala (411). Só o dono, com a sala esperando, e sem deixar `max_player`
        abaixo de quem já está sentado (jogadores ou slot ocupado)."""
        room = self.room_of(owner)
        if room is None:
            raise RoomError(RoomReason.NOT_IN_ROOM)
        if room.master != owner:
            raise RoomError(RoomReason.NOT_OWNER)
        if room.state != ROOM_WAITING:
            raise RoomError(RoomReason.STARTED)
        if not set(changes) <= SETTING_FIELDS:
            raise RoomError(RoomReason.BAD_SETTING)
        if "max_player" in changes:
            ocupados = max((m.slot + 1 for m in room.members.values()), default=0)
            if changes["max_player"] < max(len(room.members), ocupados):
                raise RoomError(RoomReason.BAD_SETTING)
        for name, value in changes.items():
            setattr(room, name, value)
        return room

    def expel(self, owner: int, target: int) -> Expelled:
        room = self.room_of(owner)
        if room is None:
            raise RoomError(RoomReason.NOT_IN_ROOM)
        if room.master != owner:
            raise RoomError(RoomReason.NOT_OWNER)
        if target == owner or target not in room.members:
            raise RoomError(RoomReason.NO_SUCH_PLAYER)
        del room.members[target]
        del self._room_of[target]
        room.in_game.discard(target)
        return Expelled(room, target)
