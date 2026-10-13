"""Salas do Channel Server em memória: criar, entrar, sair, slots, pronto, início e expulsão.

Só regras, sem bytes nem sessões: o handler (`handlers/channel/rooms.py`) traduz `RoomError` em
código de erro e monta as mensagens. Acessado só pelo loop de eventos, como o lobby (D12).
"""

from dataclasses import dataclass, field
from enum import Enum

ROOM_WAITING = 1
ROOM_PLAYING = 2
MAX_SLOTS = 70
NAME_MIN_BYTES = 3
# shortcut: 31 bytes de nome (char[32] com NUL) e 15 de senha (char[16]); tamanhos inferidos do
# layout de 301/311 (protocol/channel.py). Revisar com o hexdump do primeiro 301 real.
NAME_MAX_BYTES = 31
PASSWORD_MAX_BYTES = 15


class RoomReason(Enum):
    NOT_FOUND = "sala não existe"
    STARTED = "partida já iniciada"
    WRONG_PASSWORD = "senha inválida"
    FULL = "sala cheia"
    ALREADY_IN_ROOM = "já está em uma sala"
    NOT_IN_ROOM = "não está em sala"
    NOT_OWNER = "não é o dono da sala"
    NOT_READY = "ninguém pronto para iniciar"
    SLOT_TAKEN = "slot ocupado"
    NO_SUCH_PLAYER = "jogador não está na sala"
    BAD_NAME = "nome fora de 3..31 bytes"
    BAD_PASSWORD = "senha longa demais"


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
        room.members[owner] = RoomMember(slot=0, ready=True)
        self._rooms[room.room_id] = room
        self._room_of[owner] = room.room_id
        return room

    def join(self, room_id: int, guid: int, password: str) -> Room:
        if self.room_of(guid) is not None:
            raise RoomError(RoomReason.ALREADY_IN_ROOM)
        room = self._rooms.get(room_id)
        if room is None:
            raise RoomError(RoomReason.NOT_FOUND)
        if room.state != ROOM_WAITING:
            raise RoomError(RoomReason.STARTED)
        if room.password and room.password != password:
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
        if not room.members:
            del self._rooms[room.room_id]
            return LeaveResult(room, removed=True, new_master=None)
        if room.master != guid:
            return LeaveResult(room, removed=False, new_master=None)
        room.master = next(iter(room.members))
        return LeaveResult(room, removed=False, new_master=room.master)

    def change_slot(self, guid: int, slot: int) -> Room:
        room = self.room_of(guid)
        if room is None:
            raise RoomError(RoomReason.NOT_IN_ROOM)
        if room.state != ROOM_WAITING:
            raise RoomError(RoomReason.STARTED)
        if not 0 <= slot < room.max_player:
            raise RoomError(RoomReason.SLOT_TAKEN)
        if any(m.slot == slot for m in room.members.values()):
            raise RoomError(RoomReason.SLOT_TAKEN)
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
        room.state = ROOM_PLAYING
        return room

    def expel(self, owner: int, slot: int) -> Expelled:
        room = self.room_of(owner)
        if room is None:
            raise RoomError(RoomReason.NOT_IN_ROOM)
        if room.master != owner:
            raise RoomError(RoomReason.NOT_OWNER)
        target = next((g for g, m in room.members.items() if m.slot == slot), None)
        if target is None or target == owner:
            raise RoomError(RoomReason.NO_SUCH_PLAYER)
        del room.members[target]
        del self._room_of[target]
        return Expelled(room, target)
