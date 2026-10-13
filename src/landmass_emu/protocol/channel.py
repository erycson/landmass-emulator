"""Mensagens do Channel Server (porta 7314, net_code 14). Layouts: re/channel_server.md (§2, §3.1).

Offsets são do corpo (depois do cabeçalho `u16`). Campo sem nome no RE recebe o nome do offset.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar

from landmass_emu.protocol.message import cfield, cstr

# Texto de chat: o cliente descarta `len > 0x78` (dispatch, opcode 241).
MAX_CHAT_TEXT = 0x78

# shortcut: lobby limitado a 1600 entradas por quadro (2 + 40*1600 cabe em 65000 bytes); quando
# max_clients passar disso, paginar a lista (opcodes 545/546 do cliente, layout não decodificado).
MAX_LOBBY_ENTRIES = 1600

# Registro de sala (re/rooms.md §1 e §2; offsets relativos ao valor do nó, ver `CsRoom`).
ROOM_SLOTS = 70  # node+0x60..0x177 (`FUN_10019e90` + `0x18*4`; 421 e 549 usam o mesmo bloco)
ROOM_SPECTATORS = 60  # node+0x184..0x273
ROOM_RECORD_SIZE = 0x264  # 612: 302 copia 0x99 dwords para o nó (`disp@1312-1347`)
ROOM_HEAD_SIZE = 0x44  # 68: entrada de 141 (`disp@1039-1081`, passo 0x44)
ROOM_INFO_SIZE = 0x38  # 56: 314 lê até @0x36 + 2
ROOM_PLAYER_SIZE = 0x30  # 48: entrada de jogador de 317 (`disp@1389-1473`)
MAX_ROOM_ENTRIES = 955
MAX_ROOM_PLAYERS = 255  # `u8 count` de 317
ROOM_STATE_MASK_STATE = 0x20  # máscara de 412: bit5 = STATE (u8 @0xf)
# 312 de erro: `i32 @0` = código - 0x10000 (negativo para o cliente; `i16 @0` = código).
ERROR_JOIN_ROOM_OFFSET = 0x10000


class CsOp(IntEnum):
    HEARTBEAT = 2
    IN_CHANNEL_SERVER = 100
    IN_CHANNEL_SERVER_OUT = 101
    CHANNEL_INFO_OUT = 111
    IN_CHANNEL = 120
    IN_CHANNEL_OUT = 121
    OUT_CHANNEL = 122
    OUT_CHANNEL_OUT = 123
    CHANNEL_ROOM_INFO_OUT = 141
    CHANNEL_PLAYER_INFO_OUT = 151
    REFRESH_ROOM_LIST = 545
    REFRESH_PLAYER_LIST = 546
    REFRESH_ROOM_LIST_OUT = 547
    REFRESH_PLAYER_LIST_OUT = 548
    CREATE_ROOM = 301
    CREATE_ROOM_OUT = 302
    IN_ROOM = 311
    IN_ROOM_OUT = 312
    ROOM_INFO_OUT = 314
    ROOM_PLAYER_INFO_OUT = 317
    OUT_ROOM = 321
    OUT_ROOM_OUT = 322
    CHANGE_ROOM_MASTER_OUT = 332
    REMOVE_ROOM_OUT = 342
    READY_GAME = 401
    READY_GAME_OUT = 402
    START_GAME_OUT = 403
    CHANGE_ROOM_PROPERTY_OUT = 412
    CHANGE_ROOM_SLOT = 420
    CHANGE_ROOM_SLOT_OUT = 421
    EXPEL_PLAYER = 700
    EXPEL_PLAYER_OUT = 701
    SAVE_OPTION = 544
    SEND_MESSAGE = 240
    SEND_MESSAGE_OUT = 241
    READY_GAME_ERROR = 404
    ERROR = 54  # envelope S→C: u16 opcode real @0, i32 código @4 (NotifyErrorMessage)


@dataclass(frozen=True, slots=True)
class CsHeartbeat:
    """HEARTBEAT (2), servidor → cliente, corpo vazio. O cliente responde 2; o servidor ignora."""

    opcode: ClassVar[int] = CsOp.HEARTBEAT

    def pack(self) -> bytes:
        return b""


@dataclass(frozen=True, slots=True)
class CsInChannelServerIn:
    """IN_CHANNEL_SERVER (100): `char session_key[33]` @0 (32 hex + NUL).

    Evidência: no teste com o cliente real, o 100 chegou com 33 bytes zerados, depois de um 111 com
    33 bytes zerados. O 111 copia 33 bytes para `DAT_1005AE20` (re/message_server.md §4). Inferido:
    esses são os bytes de chave que o cliente devolve no 100. Não testado: o cliente aceitar uma
    chave não zerada."""

    session_key: str
    _SIZE = 33

    @classmethod
    def unpack(cls, payload: bytes) -> CsInChannelServerIn:
        if len(payload) < cls._SIZE:
            raise ValueError(f"CS_IN_CHANNEL_SERVER_IN curto: {len(payload)} bytes")
        return cls(cstr(payload[: cls._SIZE]))


@dataclass(frozen=True, slots=True)
class CsInChannelServerOut:
    """IN_CHANNEL_SERVER_OUT (101): corpo de 176 bytes.

    @0x00..0xa7: registro do próprio jogador (168 bytes), zeros exceto o id em @0x90 e @0xa0
    (o cliente lê o id de @0x90 como `DAT_1005ada0` e usa @0xa0 como chave do nó).
    @0xa8: `i32 result` (0 = ok). @0xac: `i32 location` (lido como `_DAT_1005ae08`; semântica
    não confirmada, o evento recebe `byte location`).

    shortcut: location fixo em 0 e `result` -160 para token recusado; confirmar no cliente real."""

    client_guid: int
    result: int
    location: int = 0
    opcode: ClassVar[int] = CsOp.IN_CHANNEL_SERVER_OUT
    _FIXED = struct.Struct("<144xi12xi4xii")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.client_guid, self.client_guid, self.result, self.location)


@dataclass(frozen=True, slots=True)
class CsChannelPlayer:
    """Registro de jogador do canal, 40 bytes: entrada de 151 (a partir de @2, stride 40) e
    corpo de 121 (@0). Campos gravados por 151 (`re/layouts_f0.md` §1.2):

    R+0x00 i32 client_guid (nó+0xa0) | R+0x04 i32 total_exp (nó+0x3c)
    R+0x08 char[16] nick, ANSI NUL-padded (nó+0x10..0x1f)
    R+0x18 u8 byte após o nick (nó+0x20) | R+0x19 u8 vehicle_licence (nó+0x23)
    R+0x1a u8 access (nó+0x21) | R+0x1c i32 clan (nó+0x28) | R+0x20 i32 clan_mark (nó+0x2c)
    R+0x24 u8 nest (nó+0x30) | R+0x25..0x27 zero.

    shortcut: total_exp, clã, marca e nest ficam zero até o marco 5 (progressão). O byte @0x18
    não tem nome no RE; fica zero."""

    client_guid: int
    nick: str = ""
    total_exp: int = 0
    unk18: int = 0
    vehicle_licence: int = 0
    access: int = 0
    clan: int = 0
    clan_mark: int = 0
    nest: int = 0
    _FIXED = struct.Struct("<ii16sBBBxiiB3x")

    def pack(self) -> bytes:
        return self._FIXED.pack(
            self.client_guid,
            self.total_exp,
            cfield(self.nick, 16),
            self.unk18,
            self.vehicle_licence,
            self.access,
            self.clan,
            self.clan_mark,
            self.nest,
        )


@dataclass(frozen=True, slots=True)
class CsInChannelOut:
    """IN_CHANNEL_OUT (121): a entrada do jogador no lobby (corpo = `CsChannelPlayer`)."""

    player: CsChannelPlayer
    opcode: ClassVar[int] = CsOp.IN_CHANNEL_OUT

    def pack(self) -> bytes:
        return self.player.pack()


@dataclass(frozen=True, slots=True)
class CsChannelInfoOut:
    """CHANNEL_INFO_OUT (111): `u8 count` @0 e `u8 load` por canal em @1+i (re/rooms.md, asm
    0x1001de7d..0x1001dea2). O nome exibido é `strChannel` + índice (texto do cliente).
    Carga: >=100 FULL (desabilitado), >80 Tumulto, >50 Bom, senão Ótimo.

    shortcut: um canal com carga 0; derivar a carga da lotação do lobby se houver mais canais."""

    loads: tuple[int, ...] = (0,)
    opcode: ClassVar[int] = CsOp.CHANNEL_INFO_OUT

    def pack(self) -> bytes:
        return bytes((len(self.loads), *self.loads))


@dataclass(frozen=True, slots=True)
class CsChannelRoomInfoOut:
    """CHANNEL_ROOM_INFO_OUT (141): `u16 count` @0 e `count` entradas de 0x44 bytes a partir de @2.
    Cada entrada é o início do registro de sala (`CsRoom.head`), ver `CsRoom`."""

    rooms: tuple[CsRoom, ...] = ()
    opcode: ClassVar[int] = CsOp.CHANNEL_ROOM_INFO_OUT
    _COUNT = struct.Struct("<H")

    def pack(self) -> bytes:
        # shortcut: lista de salas limitada a 955 entradas por quadro (2 + 68*955 cabe em 65000);
        # quando houver mais salas, paginar (opcodes 545/546, layout de paginação não decodificado).
        if len(self.rooms) > MAX_ROOM_ENTRIES:
            raise ValueError(f"salas demais para um quadro: {len(self.rooms)}")
        return self._COUNT.pack(len(self.rooms)) + b"".join(r.head() for r in self.rooms)


@dataclass(frozen=True, slots=True)
class CsChannelPlayerInfoOut:
    """CHANNEL_PLAYER_INFO_OUT (151): `u16 count` @0 e `count` entradas de 40 bytes em @2."""

    players: tuple[CsChannelPlayer, ...]
    opcode: ClassVar[int] = CsOp.CHANNEL_PLAYER_INFO_OUT
    _COUNT = struct.Struct("<H")

    def pack(self) -> bytes:
        if len(self.players) > MAX_LOBBY_ENTRIES:
            raise ValueError(f"lobby com entradas demais para um quadro: {len(self.players)}")
        return self._COUNT.pack(len(self.players)) + b"".join(p.pack() for p in self.players)


@dataclass(frozen=True, slots=True)
class CsOutChannelOut:
    """OUT_CHANNEL_OUT (123): `i32 client_guid` @0, `u8 message` @4, padding @5..7. Total 8."""

    client_guid: int
    message: int = 0
    opcode: ClassVar[int] = CsOp.OUT_CHANNEL_OUT
    _FIXED = struct.Struct("<iB3x")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.client_guid, self.message)


@dataclass(frozen=True, slots=True)
class CsSendMessageIn:
    """SEND_MESSAGE (240): `u8 msg_type` @0, `u8 len` @1, texto[len] @2. Texto em bytes."""

    msg_type: int
    text: bytes
    _HEAD = struct.Struct("<BB")

    @classmethod
    def unpack(cls, payload: bytes) -> CsSendMessageIn:
        msg_type, length = cls._HEAD.unpack_from(payload)
        if length > MAX_CHAT_TEXT or len(payload) < 2 + length:
            raise ValueError(f"CS_SEND_MESSAGE_IN inconsistente: len={length}")
        return cls(msg_type, payload[2 : 2 + length])


@dataclass(frozen=True, slots=True)
class CsSendMessageOut:
    """SEND_MESSAGE_OUT (241): `i32 sender` @0, `u8 msg_type` @4, `u8 len` @5, padding @6..7,
    texto[len] @8. Sem NUL final.

    shortcut: `msg_type` (240 @0 e 241 @4) e padding @6..7 são inferidos da assinatura do evento;
    confirmar no cliente real se o chat mostra o tipo certo e se o eco ao remetente duplica."""

    sender: int
    msg_type: int
    text: bytes
    opcode: ClassVar[int] = CsOp.SEND_MESSAGE_OUT
    _HEAD = struct.Struct("<iBBxx")

    def pack(self) -> bytes:
        if len(self.text) > MAX_CHAT_TEXT:
            raise ValueError(f"mensagem longa demais: {len(self.text)} bytes")
        return self._HEAD.pack(self.sender, self.msg_type, len(self.text)) + self.text


# ---- Salas (marco 3). Layouts e evidências: re/rooms.md §1-§8 e re/channel_server.md §2-§3. -----
# Os offsets do registro (`CsRoom`) são do corpo do 302 e relativos ao valor do nó (nó + 0x10),
# que é o que `FUN_1001d640` devolve. O 314, o 412 e o erro do 312 usam o mesmo mapa.

_I32 = struct.Struct("<i")
_I16 = struct.Struct("<h")
ROOM_JOIN_ERROR_SIZE = 0x12


@dataclass(frozen=True, slots=True)
class CsCreateRoomIn:
    """CREATE_ROOM (301), 74 bytes: `u16 map_num` @0, `char name[51]` @2, `char password[13]`
    @0x35, `u8` scale @0x42, game_mode @0x43, team_count @0x44, max_player @0x45, limit_time @0x46
    e `u16 limit_score` @0x48 (re/layouts_f0.md §7.1; confere com o hexdump do cliente real)."""

    name: str
    password: str
    scale: int
    game_mode: int
    map_num: int
    max_player: int
    team_count: int
    limit_time: int
    limit_score: int
    _FIXED = struct.Struct("<H51s13sBBBBBxH")

    @classmethod
    def unpack(cls, payload: bytes) -> CsCreateRoomIn:
        if len(payload) < cls._FIXED.size:
            raise ValueError(f"CS_CREATE_ROOM_IN curto: {len(payload)} bytes")
        map_num, raw_name, raw_pw, scale, mode, team, max_player, limit_time, limit = (
            cls._FIXED.unpack_from(payload)
        )
        return cls(
            cstr(raw_name),
            cstr(raw_pw),
            scale,
            mode,
            map_num,
            max_player,
            team,
            limit_time,
            limit,
        )


@dataclass(frozen=True, slots=True)
class CsInRoomIn:
    """IN_ROOM (311), 20 bytes: `i32 room_id` @0 e `char password[16]` @4 (5 dwords, rooms.md §2).

    shortcut: `room_id` é o guid da sala (o cliente passa `NetInRoom(num, pw)`); o tamanho da senha
    é inferido dos 5 dwords. Confirmar no cliente real."""

    room_id: int
    password: str
    _FIXED = struct.Struct("<i16s")

    @classmethod
    def unpack(cls, payload: bytes) -> CsInRoomIn:
        if len(payload) < cls._FIXED.size:
            raise ValueError(f"CS_IN_ROOM_IN curto: {len(payload)} bytes")
        room_id, raw_pw = cls._FIXED.unpack_from(payload)
        return cls(room_id, cstr(raw_pw))


@dataclass(frozen=True, slots=True)
class CsReadyGameIn:
    """READY_GAME (401): `u8 selected_morats` @0 (rooms.md §5)."""

    morats: int

    @classmethod
    def unpack(cls, payload: bytes) -> CsReadyGameIn:
        if not payload:
            raise ValueError("CS_READY_GAME_IN vazio")
        return cls(payload[0])


@dataclass(frozen=True, slots=True)
class CsChangeRoomSlotIn:
    """CHANGE_ROOM_SLOT (420): `u8 num` @0, número do slot (rooms.md §4)."""

    slot: int

    @classmethod
    def unpack(cls, payload: bytes) -> CsChangeRoomSlotIn:
        if not payload:
            raise ValueError("CS_CHANGE_ROOM_SLOT_IN vazio")
        return cls(payload[0])


@dataclass(frozen=True, slots=True)
class CsExpelPlayerIn:
    """EXPEL_PLAYER (700), 18 bytes: `i32 position` @0 (slot do alvo). O nickname não é lido.

    shortcut: rooms.md §7 deixa o mapeamento de `position` e de `u16 @16` em aberto; o slot é a
    leitura mais simples de `ExpelPlayer(position, nickname)`. Confirmar no cliente real."""

    position: int
    _FIXED = struct.Struct("<i")

    @classmethod
    def unpack(cls, payload: bytes) -> CsExpelPlayerIn:
        if len(payload) < cls._FIXED.size:
            raise ValueError(f"CS_EXPEL_PLAYER_IN curto: {len(payload)} bytes")
        return cls(cls._FIXED.unpack_from(payload)[0])


@dataclass(frozen=True, slots=True)
class CsRoom:
    """Registro de sala: corpo do 302 (612 bytes) e, nos 68 primeiros, a entrada de 141.

    Offsets (relativos ao valor do nó, rooms.md §1, §2 e §5 e o 412):
      0x00 i32 room_id (chave de busca de 302, 312, 322, 332, 342 e 412)
      0x04 u8 scale | 0x10 char[32] name | 0x30 u8 has_password (inferido)
      0x38 u8 state (1 espera, 2 jogando; 402 compara com 1) | 0x39 u8 game_mode
      0x3A u8 team_count | 0x3B u8 curr_player (conta o dono) | 0x3C u8 curr_spectator
      0x3D u8 max_player | 0x3E u8 open | 0x40 i16 map_num | 0x44 i16 limit_score
      0x46 u8 limit_time | 0x4C i32 master
      0x50 + 4*i, i < 70: guid do slot i, -1 se vazio (`ROOM_SLOTS`)
      0x174 + 4*j, j < 60: espectadores, -1 se vazio (`ROOM_SPECTATORS`)

    shortcut: name (0x10..0x2F), has_password (0x30) e scale (0x04) não têm campo decodificado no
    RE; a posição é suposição. Os demais campos seguem 412 e 314. Confirmar no cliente real."""

    room_id: int
    name: str
    has_password: bool
    state: int
    game_mode: int
    team_count: int
    curr_player: int
    max_player: int
    map_num: int
    limit_score: int
    limit_time: int
    master: int
    slots: tuple[int, ...]
    scale: int = 0
    curr_spectator: int = 0
    open: bool = True

    def pack(self) -> bytes:
        if len(self.slots) != ROOM_SLOTS:
            raise ValueError(f"sala com {len(self.slots)} slots; o registro tem {ROOM_SLOTS}")
        buf = bytearray(ROOM_RECORD_SIZE)
        _I32.pack_into(buf, 0x00, self.room_id)
        buf[0x04] = self.scale
        buf[0x10:0x30] = cfield(self.name, 32)
        buf[0x30] = int(self.has_password)
        buf[0x38] = self.state
        buf[0x39] = self.game_mode
        buf[0x3A] = self.team_count
        buf[0x3B] = self.curr_player
        buf[0x3C] = self.curr_spectator
        buf[0x3D] = self.max_player
        buf[0x3E] = int(self.open)
        _I16.pack_into(buf, 0x40, self.map_num)
        _I16.pack_into(buf, 0x44, self.limit_score)
        buf[0x46] = self.limit_time
        _I32.pack_into(buf, 0x4C, self.master)
        for i, guid in enumerate(self.slots):
            _I32.pack_into(buf, 0x50 + 4 * i, guid)
        for j in range(ROOM_SPECTATORS):
            _I32.pack_into(buf, 0x174 + 4 * j, -1)
        return bytes(buf)

    def head(self) -> bytes:
        """Entrada de 141: os primeiros 0x44 bytes do registro."""
        return self.pack()[:ROOM_HEAD_SIZE]


@dataclass(frozen=True, slots=True)
class CsCreateRoomOut:
    """CREATE_ROOM_OUT (302), 612 bytes: o registro da sala (`CsRoom.pack`). O cliente copia o
    corpo inteiro para o nó; por isso o registro sempre tem o tamanho completo."""

    room: CsRoom
    opcode: ClassVar[int] = CsOp.CREATE_ROOM_OUT

    def pack(self) -> bytes:
        return self.room.pack()


@dataclass(frozen=True, slots=True)
class CsInRoomOut:
    """IN_ROOM_OUT (312) de sucesso, 12 bytes: `i32 room_id` @0, `i32 client_guid` @4 e
    `i32 slot` @8. O cliente grava o slot no nó da sala e põe +0xa4 = room_id no jogador @4.
    Vai ao canal inteiro (rooms.md §2.3, leitura de 312 em `disp@2858-2934`)."""

    room_id: int
    client_guid: int
    slot: int
    opcode: ClassVar[int] = CsOp.IN_ROOM_OUT
    _FIXED = struct.Struct("<iii")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.room_id, self.client_guid, self.slot)


@dataclass(frozen=True, slots=True)
class CsInRoomError:
    """IN_ROOM_OUT (312) de erro, 18 bytes: `i32` @0 negativo, `i32 room_id` @4 (chave da busca) e
    a foto da sala em @8..0x0e e `i16 map` @0x10. O cliente copia essa foto no nó; zeros apagariam
    estado e modo da sala na lista.

    shortcut: o `short` do código vai para `FUN_10021c80`, cujo mapa para `msg_error` não está no RE
    (gap). Os códigos usados (1001, 1202, 1701) são os sufixos de 211000000 + código em
    `msg_error` do `landmass.wdb`. Confirmar no cliente real qual texto aparece."""

    code: int
    room_id: int
    room: CsRoom | None = None
    opcode: ClassVar[int] = CsOp.IN_ROOM_OUT

    def pack(self) -> bytes:
        buf = bytearray(ROOM_JOIN_ERROR_SIZE)
        _I32.pack_into(buf, 0, self.code - ERROR_JOIN_ROOM_OFFSET)
        _I32.pack_into(buf, 4, self.room_id)
        if self.room is not None:
            r = self.room
            buf[8] = r.state
            buf[9] = r.game_mode
            buf[10] = r.team_count
            buf[11] = r.curr_player
            buf[12] = r.curr_spectator
            buf[13] = r.max_player
            buf[14] = int(r.open)
            _I16.pack_into(buf, 0x10, r.map_num)
        return bytes(buf)


@dataclass(frozen=True, slots=True)
class CsRoomInfoOut:
    """ROOM_INFO_OUT (314), 56 bytes: estado da sala para quem entrou. Usa os mesmos campos do
    registro, com offsets do corpo: `i16 limit_score` @0, `u8 limit_time` @2, `i32 master` @8,
    `i32 room_id` @0x0c (chave de busca, `FUN_10019e90(body+0xc)`), `u8` state, mode, team, max e
    open em @0x10..0x14, `i16 map` @0x16. Depois deve vir a lista 317 completa (o 314 zera os
    slots)."""

    room: CsRoom
    opcode: ClassVar[int] = CsOp.ROOM_INFO_OUT

    def pack(self) -> bytes:
        r = self.room
        buf = bytearray(ROOM_INFO_SIZE)
        _I16.pack_into(buf, 0x00, r.limit_score)
        buf[0x02] = r.limit_time
        _I32.pack_into(buf, 0x08, r.master)
        _I32.pack_into(buf, 0x0C, r.room_id)
        buf[0x10] = r.state
        buf[0x11] = r.game_mode
        buf[0x12] = r.team_count
        buf[0x13] = r.max_player
        buf[0x14] = int(r.open)
        _I16.pack_into(buf, 0x16, r.map_num)
        return bytes(buf)


@dataclass(frozen=True, slots=True)
class CsRoomPlayer:
    """Jogador da sala, entrada de 317: 48 bytes. Os 40 primeiros são o registro de jogador do
    canal (`CsChannelPlayer`, `re/layouts_f0.md` §1.2). Depois: `u8 slot` @0x28 (índice no nó da
    sala), `u8 ready` @0x29 (bit0), `u8` flag de estado @0x2a (0: o cliente põe 0x23, em sala),
    `u8` pc_room @0x2b (zero) e `i32 morats` @0x2c (`select_morats_id`, +0xb4).

    shortcut: slot (0x28), flag (0x2a) e a posição de morats (0x2c) são inferidos do RE. A sala do
    jogador não vai na entrada: 317 a copia do próprio jogador (disp@1438). Confirmar no cliente."""

    client_guid: int
    slot: int
    ready: bool
    morats: int
    nick: str = ""
    _TAIL = struct.Struct("<BBBBi")

    def pack(self) -> bytes:
        head = CsChannelPlayer(client_guid=self.client_guid, nick=self.nick).pack()
        return head + self._TAIL.pack(self.slot, int(self.ready), 0, 0, self.morats)


@dataclass(frozen=True, slots=True)
class CsRoomPlayerInfoOut:
    """ROOM_PLAYER_INFO_OUT (317): `u8 count` @0 e `count` entradas de 48 bytes a partir de @1.
    Só vai ao jogador que entrou, logo após o 314."""

    players: tuple[CsRoomPlayer, ...]
    opcode: ClassVar[int] = CsOp.ROOM_PLAYER_INFO_OUT

    def pack(self) -> bytes:
        if len(self.players) > MAX_ROOM_PLAYERS:
            raise ValueError(f"jogadores demais para a sala: {len(self.players)}")
        return bytes((len(self.players),)) + b"".join(p.pack() for p in self.players)


@dataclass(frozen=True, slots=True)
class CsOutRoomOut:
    """OUT_ROOM_OUT (322), 8 bytes: `i32 room_id` @0 e `i32 client_guid` @4 (quem saiu ou foi
    expulso). Vai ao canal inteiro: o cliente tira o jogador da sala e o contador cai."""

    room_id: int
    client_guid: int
    opcode: ClassVar[int] = CsOp.OUT_ROOM_OUT
    _FIXED = struct.Struct("<ii")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.room_id, self.client_guid)


@dataclass(frozen=True, slots=True)
class CsChangeRoomMasterOut:
    """CHANGE_ROOM_MASTER_OUT (332), 8 bytes: `i32 room_id` @0 e `i32 new_master` @4.

    shortcut: layout inferido de `disp@2358` (body+4 vira o dono da sala, +0x5c); o rótulo é
    `NotifyChangeRoomMaster` (gap no RE). Confirmar no cliente real."""

    room_id: int
    master: int
    opcode: ClassVar[int] = CsOp.CHANGE_ROOM_MASTER_OUT
    _FIXED = struct.Struct("<ii")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.room_id, self.master)


@dataclass(frozen=True, slots=True)
class CsRemoveRoomOut:
    """REMOVE_ROOM_OUT (342), 4 bytes: `i32 room_id` @0.

    shortcut: o RE não decodifica o corpo de 342 (gap); a chave é body@0 (`disp@285-298`).
    Confirmar no cliente real que não lê mais que 4 bytes."""

    room_id: int
    opcode: ClassVar[int] = CsOp.REMOVE_ROOM_OUT

    def pack(self) -> bytes:
        return _I32.pack(self.room_id)


@dataclass(frozen=True, slots=True)
class CsReadyGameOut:
    """READY_GAME_OUT (402), 12 bytes: `i32 client_guid` @0, `u8 ready` @4, `i32 morats` @8.
    O cliente pega o jogador por @0 e põe o estado de pronto (`disp@2825-2853`)."""

    client_guid: int
    ready: bool
    morats: int
    opcode: ClassVar[int] = CsOp.READY_GAME_OUT
    _FIXED = struct.Struct("<iB3xi")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.client_guid, int(self.ready), self.morats)


@dataclass(frozen=True, slots=True)
class CsStartGameOut:
    """START_GAME_OUT (403), 18 bytes: `char address[16]` @0 (NUL-terminado) e `u16 port` @16.
    Vai só a quem está na sala.

    shortcut: os 16 bytes de endereço são hipótese (rooms.md §8: `_DAT_1005ac34..40`, 4 dwords).
    Se o cliente não conectar, a falha aparece em `OnStartGame` → `OnReadyGameError(0)`."""

    address: str
    port: int
    opcode: ClassVar[int] = CsOp.START_GAME_OUT
    _FIXED = struct.Struct("<16sH")

    def pack(self) -> bytes:
        return self._FIXED.pack(cfield(self.address, 16), self.port)


@dataclass(frozen=True, slots=True)
class CsRoomStateOut:
    """CHANGE_ROOM_PROPERTY_OUT (412), 16 bytes: `i32 room_id` @0, máscara `u8` @4 (0x20 = STATE)
    e `u8 state` @0xf. Só o campo de estado vai no quadro; os demais bits ficam zero."""

    room_id: int
    state: int
    opcode: ClassVar[int] = CsOp.CHANGE_ROOM_PROPERTY_OUT

    def pack(self) -> bytes:
        buf = bytearray(16)
        _I32.pack_into(buf, 0, self.room_id)
        buf[4] = ROOM_STATE_MASK_STATE
        buf[0xF] = self.state
        return bytes(buf)


@dataclass(frozen=True, slots=True)
class CsChangeRoomSlotOut:
    """CHANGE_ROOM_SLOT_OUT (421), 8 bytes: `i32 client_guid` @0, `u8 slot` @4."""

    client_guid: int
    slot: int
    opcode: ClassVar[int] = CsOp.CHANGE_ROOM_SLOT_OUT
    _FIXED = struct.Struct("<iB3x")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.client_guid, self.slot)


@dataclass(frozen=True, slots=True)
class CsExpelPlayerOut:
    """EXPEL_PLAYER_OUT (701), 4 bytes: `i32 result` @0 (0 = expulso)."""

    result: int = 0
    opcode: ClassVar[int] = CsOp.EXPEL_PLAYER_OUT

    def pack(self) -> bytes:
        return _I32.pack(self.result)


@dataclass(frozen=True, slots=True)
class CsErrorEnvelope:
    """Envelope de erro (opcode 54): `u16 opcode` real @0 e `i32 código` @4. O cliente mostra o
    código (`NotifyErrorMessage`, código = chave de `msg_error`) e segue o dispatch com o opcode
    real sobre o mesmo buffer.

    Use só com respostas cujo handler não lê o corpo (404, 302 e 701). O 312 não aceita envelope:
    com `u16` @0 positivo, o ramo de sucesso roda. Ver `CsInRoomError`."""

    real_opcode: int
    error: int
    opcode: ClassVar[int] = CsOp.ERROR
    # 8 bytes: o código fica em @4 (re/channel_server.md §3), não @2.
    _FIXED = struct.Struct("<H2xi")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.real_opcode, self.error)


REFRESH_PLAYER_MAX = 14  # limite de guids no pedido 546 (`FUN_10018540`)
REFRESH_ROOM_MAX = 9  # limite de salas no pedido 545 (`FUN_100183d0`)


def _guids_do_pedido(payload: bytes, maximo: int) -> tuple[int, ...]:
    """Pedidos 545/546: `i32 channel` @0 (ignorado), `u8 count` @4 (limitado a `maximo`, como o
    cliente faz), `i32 guid[count]` a partir de @8."""
    if len(payload) < 8:
        raise ValueError(f"pedido de lista curto: {len(payload)} bytes")
    count = min(payload[4], maximo)
    if len(payload) < 8 + 4 * count:
        raise ValueError(f"pedido de lista com {count} guids em {len(payload)} bytes")
    return struct.unpack_from(f"<{count}i", payload, 8)


@dataclass(frozen=True, slots=True)
class CsRefreshPlayerListIn:
    """REFRESH_PLAYER_LIST (546), 64 bytes. Ver `_guids_do_pedido`.

    shortcut: canal único; o `channel` @0 é ignorado."""

    client_guids: tuple[int, ...]

    @classmethod
    def unpack(cls, payload: bytes) -> CsRefreshPlayerListIn:
        return cls(_guids_do_pedido(payload, REFRESH_PLAYER_MAX))


@dataclass(frozen=True, slots=True)
class CsPlayerProperty:
    """Entrada de 548 (20 bytes): `i32 client_guid` @0, `i32 total_exp` @4, `i32 clan` @8,
    `i32 clan_mark` @12, `u8 nest` @16 e 3 de padding."""

    client_guid: int
    total_exp: int = 0
    clan: int = 0
    clan_mark: int = 0
    nest: int = 0
    _FIXED = struct.Struct("<iiiiB3x")

    def pack(self) -> bytes:
        return self._FIXED.pack(
            self.client_guid, self.total_exp, self.clan, self.clan_mark, self.nest
        )


@dataclass(frozen=True, slots=True)
class CsRefreshPlayerListOut:
    """NOTIFY_CHANGE_PLAYER_PROPERTY (548), resposta a 546: `u8 count` @0, 3 bytes sem uso e
    entradas de 20 bytes a partir de @4. O cliente só atualiza quem já tem nó (ver `CsRoomPlayer`
    e `CsChannelPlayer`); não cria jogador (`re/layouts_f0.md` §3.1)."""

    players: tuple[CsPlayerProperty, ...]
    opcode: ClassVar[int] = CsOp.REFRESH_PLAYER_LIST_OUT
    _HEAD = struct.Struct("<B3x")

    def pack(self) -> bytes:
        return self._HEAD.pack(len(self.players)) + b"".join(p.pack() for p in self.players)


@dataclass(frozen=True, slots=True)
class CsRefreshRoomListIn:
    """REFRESH_ROOM_LIST (545), 44 bytes. Ver `_guids_do_pedido`.

    shortcut: canal único; o `channel` @0 é ignorado."""

    room_guids: tuple[int, ...]

    @classmethod
    def unpack(cls, payload: bytes) -> CsRefreshRoomListIn:
        return cls(_guids_do_pedido(payload, REFRESH_ROOM_MAX))


@dataclass(frozen=True, slots=True)
class CsRefreshRoomListOut:
    """NOTIFY_CHANGE_ROOM_PROPERTY (547), resposta a 545: `u8 count` @0, 3 bytes sem uso e entradas
    de 16 bytes a partir de @4 (`re/layouts_f0.md` §4.2): `i32 room_guid` +0, `u8 state` +4
    (0 vazio, 1 espera, 2 jogando), `game_mode` +5, `team_count` +6, `curr_player` +7,
    `curr_spectator` +8, `max_player` +9, `open` +10, 1 de padding, `u16 map_num` +12 e 2 de
    padding.

    shortcut: `map_num` segue §4.2 (u16 em +12). O 302 grava o mapa em outro offset; o RE tem
    conflito marcado (gap). Confirmar no cliente real."""

    rooms: tuple[CsRoom, ...]
    opcode: ClassVar[int] = CsOp.REFRESH_ROOM_LIST_OUT
    _HEAD = struct.Struct("<B3x")
    _ENTRY = struct.Struct("<i7BxH2x")

    def pack(self) -> bytes:
        return self._HEAD.pack(len(self.rooms)) + b"".join(
            self._ENTRY.pack(
                r.room_id,
                r.state,
                r.game_mode,
                r.team_count,
                r.curr_player,
                r.curr_spectator,
                r.max_player,
                int(r.open),
                r.map_num,
            )
            for r in self.rooms
        )
