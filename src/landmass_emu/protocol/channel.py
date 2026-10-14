"""Mensagens do Channel Server (porta 7314, net_code 14). Layouts: re/channel_server.md (§2, §3.1).

Offsets são do corpo (depois do cabeçalho `u16`). Campo sem nome no RE recebe o nome do offset.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar

from landmass_emu.protocol.message import cfield, cstr
from landmass_emu.protocol.progression import PlayerRecord

# Texto de chat: o cliente descarta `len > 0x78` (dispatch, opcode 241).
MAX_CHAT_TEXT = 0x78

# shortcut: lobby limitado a 1600 entradas por quadro (2 + 40*1600 cabe em 65000 bytes); quando
# max_clients passar disso, paginar a lista (opcodes 545/546 do cliente, layout não decodificado).
MAX_LOBBY_ENTRIES = 1600

# Registro de sala (re/rooms.md §1 e §2; offsets relativos ao valor do nó, ver `CsRoom`).
ROOM_SLOTS = 70  # node+0x60..0x177 (`FUN_10019e90` + `0x18*4`; 421 e 549 usam o mesmo bloco)
ROOM_SPECTATORS = 60  # node+0x184..0x273; sem uso confirmado, sempre -1 (espectador é slot 60..69)
ROOM_RECORD_SIZE = 0x264  # 612: 302 copia 0x99 dwords para o nó (`disp@1312-1347`)
ROOM_HEAD_SIZE = 0x44  # 68: entrada de 141 (`disp@1039-1081`, passo 0x44)
ROOM_INFO_SIZE = 0x38  # 56: 314 lê até @0x36 + 2
ROOM_PLAYER_SIZE = 0x30  # 48: entrada de jogador de 317 (`disp@1389-1473`)
MAX_ROOM_ENTRIES = 955
MAX_ROOM_PLAYERS = 255  # `u8 count` de 317
# Bits de 411 (`flags`) e de 412 (`mask`): os mesmos (dispatcher `0x19c`, re/layouts_f0.md §7.2).
ROOM_FLAG_MAP = 0x01  # map_num: u16 @2 em 411; i16 @6 em 412
ROOM_FLAG_MODE = 0x02  # game_mode @4 e team_count @5 em 411; @8 e @9 em 412
ROOM_FLAG_LIMIT_PLAYER = 0x04  # max_player: u8 @6 em 411; @0xa em 412
ROOM_FLAG_LIMIT_SCORE = 0x08  # limit_score: u16 @8 em 411; i16 @0xc em 412
ROOM_FLAG_LIMIT_TIME = 0x10  # limit_time: u8 @7 em 411; @0xb em 412
ROOM_FLAG_STATE = 0x20  # só em 412: state u8 @0xf
ROOM_FLAG_OPEN = 0x40  # só em 412: open u8 @0xe
NICK_SIZE = 17  # char[17] de nick nos pedidos 451, 461 e 700 e no convite 463 (este inferido)
ROOM_NAME_SIZE = 51  # char[51] do nome: 301 (@2) e o registro de sala (@4, até @0x36)
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
    GET_CHANNEL_PLAYER_INFO = 464  # sem corpo; resposta 151 (lista do lobby)
    PLAYER_DETAIL_IN = 542
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
    CHANGE_ROOM_PROPERTY = 411
    CHANGE_ROOM_PROPERTY_OUT = 412
    CHANGE_ROOM_SLOT = 420
    CHANGE_ROOM_SLOT_OUT = 421
    ROOM_EXPEL = 451  # sem resposta: o 452 não tem caso no dispatcher
    ROOM_INVITE = 461
    ROOM_INVITE_OUT = 462
    ROOM_INVITE_NOTIFY = 463
    ROOM_INVITE_ANSWER = 471
    PLAYER_DETAIL_OUT = 543
    ROOM_ENTRY_OUT = 549
    ENTER_HANGAR = 586
    ENTER_HANGAR_OUT = 587
    LEAVE_HANGAR = 588
    LEAVE_HANGAR_OUT = 589
    EXPEL_PLAYER = 700
    EXPEL_PLAYER_OUT = 701
    EXIT_PLAY = 500
    EXIT_PLAY_OUT = 501
    SAVE_OPTION = 544
    SEND_MESSAGE = 240
    SEND_MESSAGE_OUT = 241
    SEND_COMMAND = 250  # /NOTIFY e /ALLNOTIFY do console GM (D193)
    SEND_COMMAND_OUT = 251
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

    @0x00..0xa7: registro do próprio jogador (168 bytes, `PlayerRecord`). Os campos de progressão
    vêm do banco; os demais são zero, e o id fica em @0x90 e @0xa0 (o cliente lê o id de @0x90
    como `DAT_1005ada0` e usa @0xa0 como chave do nó).
    @0xa8: `i32 result` (0 = ok). @0xac: `i32 location` (lido como `_DAT_1005ae08`; semântica
    não confirmada, o evento recebe `byte location`).

    shortcut: location fixo em 0 e `result` -160 para token recusado; confirmar no cliente real."""

    client_guid: int
    result: int
    location: int = 0
    progress: PlayerRecord = PlayerRecord()
    opcode: ClassVar[int] = CsOp.IN_CHANNEL_SERVER_OUT
    _TAIL = struct.Struct("<ii")

    def pack(self) -> bytes:
        return self.progress.pack(self.client_guid) + self._TAIL.pack(self.result, self.location)


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


@dataclass(frozen=True, slots=True)
class CsSendCommandIn:
    """SEND_COMMAND (250): `u8 todos` @0 (1 = `/ALLNOTIFY`, 0 = `/NOTIFY`), `u8 len` @1, texto[len]
    @2. Evidência: `FUN_100173b0` grava 'Y' como 1 e corta o texto em 0x78; `FUN_10001790` copia
    os 2 bytes de cabeçalho e `len` bytes de texto (`re/layouts_f0.md` §7.6, `protocol_full.md`)."""

    all_server: bool
    text: bytes
    _HEAD = struct.Struct("<BB")

    @classmethod
    def unpack(cls, payload: bytes) -> CsSendCommandIn:
        if len(payload) < cls._HEAD.size:
            raise ValueError(f"CS_SEND_COMMAND_IN curto: {len(payload)} bytes")
        flag, length = cls._HEAD.unpack_from(payload)
        if length > MAX_CHAT_TEXT or len(payload) < cls._HEAD.size + length:
            raise ValueError(f"CS_SEND_COMMAND_IN inconsistente: len={length}")
        return cls(flag != 0, payload[2 : 2 + length])


@dataclass(frozen=True, slots=True)
class CsSendCommandOut:
    """SEND_COMMAND_OUT (251): `u8 len` @0, texto[len] @1 e NUL logo depois.

    Evidência: o case 0xfb de `re/LM_Engine.dll/channel_dispatch_FUN_1001da60.c` (L1281-1311) lê
    `*param_2` como tamanho e copia esse número de bytes de `param_2 + 1`; o `NotifySendCommand`
    recebe o ponteiro do texto, lido como C string. O `re/protocol_full.md` chama @0 de "comando",
    mas o código o usa como tamanho. O cliente não usa o byte de flag do pedido.
    """

    text: bytes
    opcode: ClassVar[int] = CsOp.SEND_COMMAND_OUT

    def pack(self) -> bytes:
        if len(self.text) > MAX_CHAT_TEXT:
            raise ValueError(f"aviso longo demais: {len(self.text)} bytes")
        return bytes((len(self.text),)) + self.text + b"\x00"


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
    """CHANGE_ROOM_SLOT (420): `u8 team` @0, o grupo novo (`ChangeTeam` manda `slot % team_count`;
    `re/rooms.md` §4). O servidor escolhe o slot livre dentro do grupo."""

    team: int

    @classmethod
    def unpack(cls, payload: bytes) -> CsChangeRoomSlotIn:
        if not payload:
            raise ValueError("CS_CHANGE_ROOM_SLOT_IN vazio")
        return cls(payload[0])


@dataclass(frozen=True, slots=True)
class CsExpelPlayerIn:
    """EXPEL_PLAYER (700), 18 bytes: `u8 kind` @0 e `char nick[17]` @1 (wrapper `0x10017bb0`).

    `kind`: 0x10 WEB, 0x21 CHANNEL, 0x22 LOBBY (`FUN_10017bb0`). É o `/EXPEL` do console
    (`XInterface` L21281), não a expulsão do dono da sala (essa é o 451). Quem pede precisa de
    `ucAccess` 9 ou mais (`domain/access.py`); o servidor confere.

    Evidência do cliente: `ExpelPlayer` grava `_DAT_1005aa54 = -1` antes do pedido, e o 701 grava o
    resultado nessa mesma variável. Por isso o 701 é resposta a quem pediu (D193)."""

    kind: int
    nickname: str

    @classmethod
    def unpack(cls, payload: bytes) -> CsExpelPlayerIn:
        if len(payload) < 1 + NICK_SIZE:
            raise ValueError(f"CS_EXPEL_PLAYER_IN curto: {len(payload)} bytes")
        return cls(payload[0], cstr(payload[1 : 1 + NICK_SIZE]))

    def pack(self) -> bytes:
        return bytes((self.kind,)) + cfield(self.nickname, NICK_SIZE)


@dataclass(frozen=True, slots=True)
class CsRoomExpelIn:
    """ROOM_EXPEL (451), 18 bytes: `@0` não é preenchido pelo cliente (lixo, ignorado) e
    `char nick[17]` @1 (wrapper `0x10017a10`). Pedido do dono da sala. A resposta 452 não tem caso
    no dispatcher, então não há resposta. A UI não chama (`XInterface` L29174, comentado)."""

    nickname: str

    @classmethod
    def unpack(cls, payload: bytes) -> CsRoomExpelIn:
        if len(payload) < 1 + NICK_SIZE:
            raise ValueError(f"CS_ROOM_EXPEL_IN curto: {len(payload)} bytes")
        return cls(cstr(payload[1 : 1 + NICK_SIZE]))

    def pack(self) -> bytes:
        return b"\0" + cfield(self.nickname, NICK_SIZE)


@dataclass(frozen=True, slots=True)
class CsRoomInviteIn:
    """ROOM_INVITE (461), 17 bytes: `char nick[17]` @0, NUL-terminado (wrapper `0x10017a90`).
    Só o dono convida (`NetRoomInvite`, `XInterface` L17344)."""

    nickname: str

    @classmethod
    def unpack(cls, payload: bytes) -> CsRoomInviteIn:
        if len(payload) < NICK_SIZE:
            raise ValueError(f"CS_ROOM_INVITE_IN curto: {len(payload)} bytes")
        return cls(cstr(payload[:NICK_SIZE]))


@dataclass(frozen=True, slots=True)
class CsInviteResultOut:
    """ROOM_INVITE_OUT (462), 4 bytes: `i32 result` @0, resposta ao convidador. 0 = convite
    enviado; CERR negativo = recusado (`re/layouts_f0.md` §7.3). O envelope de -4061 (quem não é
    dono) não mostra nada no cliente (dispatcher `0x1ce`, `disp@407-415`)."""

    result: int
    opcode: ClassVar[int] = CsOp.ROOM_INVITE_OUT
    _FIXED = struct.Struct("<i")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.result)


@dataclass(frozen=True, slots=True)
class CsRoomInviteOut:
    """ROOM_INVITE_NOTIFY (463), ao convidado: `i32 room_guid` @0 (vira `DAT_1005aa90`, a sala do
    aceite sem argumento) e `char nick[17]` @4 com o nick de quem convida (`NotifyRoomInvite(int,
    string)`, wrapper `0x100044f0`, que lê de @4 até NUL).

    shortcut: os 17 bytes de @4 são inferidos dos demais nicks (o RE não os fixa); o cliente lê
    até NUL. Revisar na primeira captura de convite."""

    room_id: int
    inviter: str
    opcode: ClassVar[int] = CsOp.ROOM_INVITE_NOTIFY
    _FIXED = struct.Struct("<i")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.room_id) + cfield(self.inviter, NICK_SIZE)


@dataclass(frozen=True, slots=True)
class CsRoomInviteAnswerIn:
    """ROOM_INVITE_ANSWER (471): `i32 room_id` @0 e `u8 accept` @4 (1 se o cliente mandou 'Y' ou
    'y'). @5..7 não são preenchidos pelo cliente (lixo, ignorado). Wrapper `0x10017b10`."""

    room_id: int
    accept: bool
    _FIXED = struct.Struct("<iB")

    @classmethod
    def unpack(cls, payload: bytes) -> CsRoomInviteAnswerIn:
        if len(payload) < cls._FIXED.size:
            raise ValueError(f"CS_ROOM_INVITE_ANSWER_IN curto: {len(payload)} bytes")
        room_id, accept = cls._FIXED.unpack_from(payload)
        return cls(room_id, bool(accept))

    def pack(self) -> bytes:
        return self._FIXED.pack(self.room_id, int(self.accept)) + bytes(3)


@dataclass(frozen=True, slots=True)
class CsRoom:
    """Registro de sala: corpo do 302 (612 bytes) e, nos 68 primeiros, a entrada de 141.

    Offsets relativos ao valor do nó (nó + 0x10), o que `execGetRoomInfo` lê (`LM_Engine`
    `0x10008000`, com a ordem de `LM_ROOM_INFO` em `LM_Engine.src.txt`):
      0x00 i32 room_id (chave de busca de 302, 312, 322, 332, 342 e 412)
      0x04 char[51] name, NUL-terminado (o cliente lê até NUL; 301 limita a 50 bytes + NUL)
      0x37 u8 has_password (bool `password` do `LM_ROOM_INFO`)
      0x38 u8 state (0 espera, 1 jogando; RS_WAITING e RS_PLAYING) | 0x39 u8 game_mode
      0x3A u8 team_count | 0x3B u8 curr_player (conta o dono) | 0x3C u8 curr_spectator
      0x3D u8 max_player | 0x3E u8 open | 0x40 i16 map_num | 0x44 i16 limit_score
      0x46 u8 limit_time | 0x47 u8 game_scale | 0x48 u8 team_damage (zero aqui)
      0x4C i32 master
      0x50 + 4*i, i < 70: guid do slot i, -1 se vazio (`ROOM_SLOTS`). Slots 60..69 são de
          espectador (D197): o cliente lê `MySlot >= 60` nessa lista
      0x174 + 4*j, j < 60: bloco sem uso confirmado (provável `enemy_player[MAX_ROOM_PLAYER]`);
          sai sempre -1 (`ROOM_SPECTATORS`)

    shortcut: a entrada de 141 tem 0x44 bytes, então a escala (0x47) não chega à lista do lobby:
    a sala aparece com escala 0 até o 302 ou o 314 da sala. Revisar com captura da lista."""

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
        buf[0x04 : 0x04 + ROOM_NAME_SIZE] = cfield(self.name, ROOM_NAME_SIZE)
        buf[0x37] = int(self.has_password)
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
        buf[0x47] = self.scale
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
    registro, com offsets do corpo: `i16 limit_score` @0, `u8 limit_time` @2, `u8 game_scale` @3
    (node+0x57, confirmado pelo `execGetRoomInfo`), `i32 master` @8, `i32 room_id` @0x0c (chave de
    busca, `FUN_10019e90(body+0xc)`), `u8` state, mode, team, max e open em @0x10..0x14, `i16 map`
    @0x16. Não leva a senha: o 314 não grava o bit de senha (0x37). Depois deve vir a lista 317
    completa (o 314 zera os slots)."""

    room: CsRoom
    opcode: ClassVar[int] = CsOp.ROOM_INFO_OUT

    def pack(self) -> bytes:
        r = self.room
        buf = bytearray(ROOM_INFO_SIZE)
        _I16.pack_into(buf, 0x00, r.limit_score)
        buf[0x02] = r.limit_time
        buf[0x03] = r.scale
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

    Usada em 317 (lista da sala) e em 549 (entrada de quem chegou; mesmo registro de 48 bytes).

    shortcut: slot (0x28), flag (0x2a) e a posição de morats (0x2c) são inferidos do RE. A sala do
    jogador não vai na entrada: 317 e 549 a copiam do próprio jogador (disp@1438, disp@650).
    Confirmar no cliente."""

    client_guid: int
    slot: int
    ready: bool
    morats: int
    nick: str = ""
    total_exp: int = 0
    access: int = 0
    _TAIL = struct.Struct("<BBBBi")

    def pack(self) -> bytes:
        head = CsChannelPlayer(
            client_guid=self.client_guid,
            nick=self.nick,
            total_exp=self.total_exp,
            access=self.access,
        ).pack()
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
    """CHANGE_ROOM_MASTER_OUT (332), 8 bytes: `i32 room_guid` @0 e `i32 client_guid` @4 (novo
    dono). Ordem pela assinatura `NotifyChangeRoomMaster(int room_guid, int client_guid)`
    (re/protocol_full.md §7, item 7).

    shortcut: a ordem vem da assinatura do evento, sem captura; o efeito no nó (+0x5c) não está
    confirmado. Revisar na primeira troca de dono capturada."""

    room_id: int
    master: int
    opcode: ClassVar[int] = CsOp.CHANGE_ROOM_MASTER_OUT
    _FIXED = struct.Struct("<ii")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.room_id, self.master)


@dataclass(frozen=True, slots=True)
class CsRemoveRoomOut:
    """REMOVE_ROOM_OUT (342), 4 bytes: `i32 room_guid` @0 (assinatura `NotifyRemoveRoom(int
    room_guid)`, re/protocol_full.md §7, item 7).

    shortcut: os 4 bytes vêm da assinatura do evento; sem captura de 342 para confirmar que o
    cliente não lê mais que isso. Revisar na primeira captura de sala removida."""

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
class CsEnterHangarOut:
    """ENTER_HANGAR_OUT (587), 4 bytes: `i32 client_guid` @0, a chave de quem entrou no hangar.
    O cliente abre o hangar só quando a chave é a própria (`NotifyEnterHanger`, XInterface 28991).
    Não há corpo na entrada (586)."""

    client_guid: int
    opcode: ClassVar[int] = CsOp.ENTER_HANGAR_OUT

    def pack(self) -> bytes:
        return _I32.pack(self.client_guid)


@dataclass(frozen=True, slots=True)
class CsLeaveHangarOut:
    """LEAVE_HANGAR_OUT (589), 8 bytes: `i32 client_guid` @0 e `u8 position` @4. O cliente volta à
    página da sala só com a chave própria e a posição 0x23 (dispatcher `case 0x24d`, re/rooms.md
    §12). O tamanho de 8 bytes é inferido: o dispatcher lê até o byte 4."""

    client_guid: int
    opcode: ClassVar[int] = CsOp.LEAVE_HANGAR_OUT
    ROOM_POSITION: ClassVar[int] = 0x23
    _FIXED = struct.Struct("<iB3x")

    def pack(self) -> bytes:
        return self._FIXED.pack(self.client_guid, self.ROOM_POSITION)


@dataclass(frozen=True, slots=True)
class CsStartGameOut:
    """START_GAME_OUT (403), 18 bytes: `char address[16]` @0 (NUL-terminado) e `u16 port` @16.
    Vai só a quem está na sala.

    Conversão fechada em `NotifyStartGame_0x10004440.c` (endereço = C-string de @0..15, porta = u16
    @0x10). shortcut: a ligação aos parâmetros do evento é inferida; se o cliente não conectar, a
    falha aparece em `OnStartGame` → `OnReadyGameError(0)`."""

    address: str
    port: int
    opcode: ClassVar[int] = CsOp.START_GAME_OUT
    _FIXED = struct.Struct("<16sH")

    def pack(self) -> bytes:
        return self._FIXED.pack(cfield(self.address, 16), self.port)


@dataclass(frozen=True, slots=True)
class CsChangeRoomPropertyIn:
    """CHANGE_ROOM_PROPERTY (411), corpo de 10 bytes (wrapper `FUN_10017820`,
    re/layouts_f0.md §7.2): `u8 flags` @0; `u16 map_num` @2 (se MAP); `u8 game_mode` @4 e
    `u8 team_count` @5 (se MODE); `u8 max_player` @6; `u8 limit_time` @7; `u16 limit_score` @8.
    @1 e @9 não são usados.

    Os bits de `flags` dizem o que mudar. O cliente sempre manda max, tempo e pontos, mas só
    valem os campos com bit ligado.

    shortcut: o RE diz que max, tempo e pontos são sempre escritos; o emulador só os aplica com o
    bit ligado. Revisar na primeira captura de troca de configuração."""

    flags: int
    map_num: int
    game_mode: int
    team_count: int
    max_player: int
    limit_time: int
    limit_score: int
    _FIXED = struct.Struct("<BxHBBBBH")

    @classmethod
    def unpack(cls, payload: bytes) -> CsChangeRoomPropertyIn:
        if len(payload) < cls._FIXED.size:
            raise ValueError(f"CS_CHANGE_ROOM_PROPERTY_IN curto: {len(payload)} bytes")
        flags, map_num, mode, team, max_player, limit_time, limit = cls._FIXED.unpack_from(payload)
        return cls(flags, map_num, mode, team, max_player, limit_time, limit)


@dataclass(frozen=True, slots=True)
class CsChangeRoomPropertyOut:
    """CHANGE_ROOM_PROPERTY_OUT (412), 16 bytes: `i32 room_id` @0 (chave de busca), `u8 mask` @4
    e os campos dos bits ligados (dispatcher `0x19c`, `disp@352-381`): MAP `i16 @6`; MODE
    `game_mode @8` e `team_count @9`; LIMIT_PLAYER `u8 @0xa`; LIMIT_TIME `u8 @0xb`; LIMIT_SCORE
    `i16 @0xc`; OPEN `u8 @0xe`; STATE `u8 @0xf`. Campo `None` fica de fora da máscara e não muda
    no cliente. Os nomes seguem o nó que cada campo grava (`execGetRoomInfo`: limit_time é
    nó+0x46, map é nó+0x50)."""

    room_id: int
    map_num: int | None = None
    game_mode: int | None = None
    team_count: int | None = None
    max_player: int | None = None
    limit_time: int | None = None
    limit_score: int | None = None
    is_open: bool | None = None
    state: int | None = None
    opcode: ClassVar[int] = CsOp.CHANGE_ROOM_PROPERTY_OUT

    def pack(self) -> bytes:
        if (self.game_mode is None) != (self.team_count is None):
            raise ValueError("MODE exige game_mode e team_count juntos")
        buf = bytearray(16)
        _I32.pack_into(buf, 0, self.room_id)
        mask = 0
        if self.map_num is not None:
            mask |= ROOM_FLAG_MAP
            _I16.pack_into(buf, 6, self.map_num)
        if self.game_mode is not None and self.team_count is not None:
            mask |= ROOM_FLAG_MODE
            buf[8] = self.game_mode
            buf[9] = self.team_count
        if self.max_player is not None:
            mask |= ROOM_FLAG_LIMIT_PLAYER
            buf[0xA] = self.max_player
        if self.limit_time is not None:
            mask |= ROOM_FLAG_LIMIT_TIME
            buf[0xB] = self.limit_time
        if self.limit_score is not None:
            mask |= ROOM_FLAG_LIMIT_SCORE
            _I16.pack_into(buf, 0xC, self.limit_score)
        if self.is_open is not None:
            mask |= ROOM_FLAG_OPEN
            buf[0xE] = int(self.is_open)
        if self.state is not None:
            mask |= ROOM_FLAG_STATE
            buf[0xF] = self.state
        buf[4] = mask
        return bytes(buf)


@dataclass(frozen=True, slots=True)
class CsRoomEntryOut:
    """ROOM_ENTRY_OUT (549), 48 bytes: o registro de quem entrou (`CsRoomPlayer`, o mesmo de 317).
    Vai só a quem já está na sala. O cliente cria o nó do entrante, grava o slot na sala de quem
    recebe e soma 1 no contador de jogadores (`disp@608-691`). Por isso não vai a quem recebe 312,
    que também soma: ver `RoomHandlers._joined`.

    shortcut: a divisão de quem recebe 549 e quem recebe 312 é decisão deste servidor (o RE mostra
    os dois efeitos, não quem os envia em cada caso). Revisar na primeira captura com dois clientes
    na sala."""

    player: CsRoomPlayer
    opcode: ClassVar[int] = CsOp.ROOM_ENTRY_OUT

    def pack(self) -> bytes:
        return self.player.pack()


@dataclass(frozen=True, slots=True)
class CsPlayerDetailIn:
    """PLAYER_DETAIL_IN (542), 17 bytes: `char nick[17]` @0, NUL-terminado (wrapper `0x10017d50`).
    É o clique no nick da lista (`NetDetailPlayerInfo`); a resposta é o 543."""

    nickname: str

    @classmethod
    def unpack(cls, payload: bytes) -> CsPlayerDetailIn:
        if len(payload) < NICK_SIZE:
            raise ValueError(f"CS_PLAYER_DETAIL_IN curto: {len(payload)} bytes")
        return cls(cstr(payload[:NICK_SIZE]))


@dataclass(frozen=True, slots=True)
class CsPlayerDetailOut:
    """PLAYER_DETAIL_OUT (543): corpo de `LM_PLAYER_DETAIL_INFO` (evento `NotifyDetailPlayerInfo`,
    `result` vem do envelope, não do corpo). Ordem da struct em `LM_Engine.src.txt` (L722): nick;
    oito `i32` a partir de @0x14 (`nTotalRank`, `nTotalGamecount`, `nTotalWin`, `nTotalLose`,
    `nTotalKill`, `nTotalDeath`, `nHeadshot`, `nTotalExp`); `u8 ucNest` @0x34; `i32 nClanMark`
    @0x38; `strClanName` @0x3c, NUL-terminado. A ficha (`LM_PlayerInfoPage.OnDetailPlayerInfo`,
    `XInterface.src.txt` L32768) mostra o nest, a patente pelo exp, "Desertado" por
    `(jogos - vitórias - derrotas) * 100 / jogos` e o clã só com `nClanMark > -1` e nome não vazio.

    shortcut: o tamanho do nick (20 bytes) e do clã (17) é inferido: a struct não fixa. Os valores
    vêm do banco pelo handler (`ListHandlers.player_detail`, D107)."""

    nickname: str
    rank: int = 0
    games: int = 0
    wins: int = 0
    losses: int = 0
    kills: int = 0
    deaths: int = 0
    headshots: int = 0
    total_exp: int = 0
    nest: int = 0
    clan_mark: int = 0
    clan: str = ""
    opcode: ClassVar[int] = CsOp.PLAYER_DETAIL_OUT
    _INTS = struct.Struct("<8i")

    def pack(self) -> bytes:
        head = bytearray(0x3C)
        head[0:0x14] = cfield(self.nickname, 0x14)
        self._INTS.pack_into(
            head,
            0x14,
            self.rank,
            self.games,
            self.wins,
            self.losses,
            self.kills,
            self.deaths,
            self.headshots,
            self.total_exp,
        )
        head[0x34] = self.nest
        _I32.pack_into(head, 0x38, self.clan_mark)
        return bytes(head) + cfield(self.clan, NICK_SIZE)


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
class CsExitPlayOut:
    """EXIT_PLAY_OUT (501), 4 bytes: `i32 result` @0. Resposta a 500 (EXIT_PLAY, corpo vazio).
    shortcut: valor 0 não confirmado no cliente; ver re/game_server_host.md."""

    result: int = 0
    opcode: ClassVar[int] = CsOp.EXIT_PLAY_OUT

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
    (0 espera, 1 jogando), `game_mode` +5, `team_count` +6, `curr_player` +7,
    `curr_spectator` +8, `max_player` +9, `open` +10, 1 de padding, `u16 map_num` +12 e 2 de
    padding.

    shortcut: `map_num` (u16 em +12, nó+0x50) é o mesmo campo que 302, 314 e 412 gravam, segundo
    `execGetRoomInfo`. Falta captura de 547 para confirmar a leitura."""

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
