"""Partida no Channel Server com servidor de partida falso: início (401 com 412 e 403), falha
(241000201), fim pelo último 500, queda do servidor, saída da última pessoa em jogo, volta à sala e
gravação do histórico. O servidor real é coberto em `test_match_host.py`."""

import asyncio
import struct
from collections.abc import Awaitable, Callable

from test_channel_handlers import _corpos, _criar_sala, _entra_no_lobby, _Mapas

from landmass_emu.domain.lobby import Lobby
from landmass_emu.domain.match import MapRecord, MatchPlan
from landmass_emu.domain.match_stats import GameEndedPlayer, MatchRecord
from landmass_emu.domain.progression import Progression
from landmass_emu.domain.rooms import ROOM_PLAYING, ROOM_WAITING, Room, Rooms
from landmass_emu.handlers.channel.records import ChannelRecords
from landmass_emu.handlers.channel.rooms import ERR_MATCH_START, RoomHandlers
from landmass_emu.net.session import Session
from landmass_emu.ports.match_host import GameEndpoint, MapCatalog, MatchStartError
from landmass_emu.protocol.channel import (
    ROOM_FLAG_STATE,
    CsErrorEnvelope,
    CsExitPlayOut,
    CsInRoomOut,
    CsLeaveHangarOut,
    CsOp,
    CsRoomInfoOut,
    CsRoomPlayerInfoOut,
)
from landmass_emu.protocol.progression import CsProgressionOp


class _HostFalso:
    """Servidor de partida sem processo. `falha` faz o início recusar, como a porta ocupada."""

    def __init__(self, falha: str | None = None, bloco: tuple[GameEndedPlayer, ...] = ()) -> None:
        self._falha = falha
        self._bloco = bloco
        self.iniciados: list[tuple[int, MatchPlan]] = []
        self.encerrados: list[int] = []
        self.on_exit: Callable[[], Awaitable[None]] | None = None

    async def start(
        self, room_id: int, plan: MatchPlan, on_exit: Callable[[], Awaitable[None]]
    ) -> GameEndpoint:
        if self._falha is not None:
            raise MatchStartError(self._falha)
        self.iniciados.append((room_id, plan))
        self.on_exit = on_exit
        return GameEndpoint("10.0.0.5", 7800)

    def finish(self, room_id: int) -> None:
        self.encerrados.append(room_id)

    async def end(self, room_id: int) -> tuple[GameEndedPlayer, ...]:
        self.encerrados.append(room_id)
        return self._bloco

    async def close(self) -> None:
        return None


class _Historico:
    """Repositório em memória: guarda o que foi gravado."""

    def __init__(self) -> None:
        self.salvos: list[MatchRecord] = []

    async def save(self, match: MatchRecord) -> int:
        self.salvos.append(match)
        return len(self.salvos)


class _SemMapas:
    def get(self, record_id: int) -> MapRecord | None:
        return None


class _Progressao:
    """Saldos em memória, como o banco fica depois da gravação da partida."""

    def __init__(self, saldos: dict[int, Progression]) -> None:
        self._saldos = saldos

    async def get(self, account_id: int) -> Progression:
        return self._saldos[account_id]


class _Auditoria:
    """Guarda (evento, conta, campos) de cada linha de economia."""

    def __init__(self) -> None:
        self.linhas: list[tuple[str, int, dict[str, object]]] = []

    def record_account(self, account_id: int, nickname: str, event: str, **fields: object) -> None:
        self.linhas.append((event, account_id, fields))


def _montagem(
    host: _HostFalso,
    historico: _Historico | None = None,
    maps: MapCatalog | None = None,
    progressao: _Progressao | None = None,
    auditoria: _Auditoria | None = None,
) -> tuple[RoomHandlers, Lobby, Rooms]:
    lobby = Lobby()
    rooms = Rooms()
    handlers = RoomHandlers(
        lobby,
        rooms,
        ChannelRecords(lobby),
        host,
        maps or _Mapas(),
        historico,
        progression=progressao,
        audit=auditoria,
    )
    return handlers, lobby, rooms


async def _partida(
    handlers: RoomHandlers, lobby: Lobby, rooms: Rooms
) -> tuple[Session, Session, Room]:
    """Ana (dona, guid 7) e Bia (guid 9) na sala, Bia pronta, e Ana inicia a partida."""
    ana = _entra_no_lobby(lobby, 7, "Ana")
    bia = _entra_no_lobby(lobby, 9, "Bia")
    sala = _criar_sala(rooms, 7)
    rooms.join(sala.room_id, 9, "")
    await handlers.ready_game(bia, bytes([0]))
    await handlers.ready_game(ana, bytes([0]))
    return ana, bia, sala


async def test_fim_com_bloco_gameended_grava_exp_e_ld_avisa_saldo_e_audita() -> None:
    bloco = (
        GameEndedPlayer(
            nickname="Ana",
            reason="TimeLimit",
            kills=12,
            ranking=1,
            played_percent=100.0,
            total_exp=3341,
            total_money=1710,
            winner=None,
            mission_score=None,
        ),
    )
    host = _HostFalso(bloco=bloco)
    historico = _Historico()
    progressao = _Progressao({7: Progression(total_exp=3341, ld=1710, cash=50)})
    auditoria = _Auditoria()
    handlers, lobby, rooms = _montagem(host, historico, progressao=progressao, auditoria=auditoria)
    ana, bia, _sala = await _partida(handlers, lobby, rooms)

    await handlers.exit_play(ana, b"")
    await handlers.exit_play(bia, b"")  # último em jogo: a partida acaba e grava

    [partida] = historico.salvos
    ana_gravada, bia_gravada = partida.players
    assert (ana_gravada.kills, ana_gravada.exp, ana_gravada.money) == (12, 3341, 1710)
    assert (bia_gravada.exp, bia_gravada.money) == (None, None)
    assert [(evento, conta) for evento, conta, _ in auditoria.linhas] == [("match_reward", 7)]
    ops = [op for op, _ in _corpos(ana)]
    assert CsProgressionOp.CHARGE_CASH_OUT in ops
    assert CsProgressionOp.CHARGE_POINT_OUT in ops


async def test_401_do_dono_sobe_a_partida_e_so_depois_manda_403_aos_da_sala() -> None:
    host = _HostFalso()
    handlers, lobby, rooms = _montagem(host, _Historico())
    _ana, bia, sala = await _partida(handlers, lobby, rooms)

    [(room_id, plano)] = host.iniciados
    assert room_id == sala.room_id
    assert (plano.map_file, plano.game_class) == ("ONS-Treino", "XGame.LM_TeamOperation")
    # Bia recebe: 402 de Bia pronta, 412 PLAYING ao canal, 402 do dono pronto (D77) e 403 com o
    # endereço do servidor.
    recebidos = _corpos(bia)
    assert [op for op, _ in recebidos] == [
        CsOp.READY_GAME_OUT,
        CsOp.CHANGE_ROOM_PROPERTY_OUT,
        CsOp.READY_GAME_OUT,
        CsOp.START_GAME_OUT,
    ]
    assert recebidos[1][1][0xF] == ROOM_PLAYING
    assert struct.unpack_from("<iB", recebidos[2][1], 0) == (7, 1)
    inicio = recebidos[3][1]
    assert inicio.split(b"\0")[0] == b"10.0.0.5"
    assert struct.unpack_from("<H", inicio, 16) == (7800,)


async def test_falha_ao_subir_servidor_volta_a_sala_a_espera_e_erra_para_o_dono() -> None:
    host = _HostFalso(falha="porta ocupada")
    historico = _Historico()
    handlers, lobby, rooms = _montagem(host, historico)
    ana = _entra_no_lobby(lobby, 7, "Ana")
    bia = _entra_no_lobby(lobby, 9, "Bia")
    sala = _criar_sala(rooms, 7)
    rooms.join(sala.room_id, 9, "")
    await handlers.ready_game(bia, bytes([0]))
    _corpos(ana)
    _corpos(bia)

    respostas = await handlers.ready_game(ana, bytes([0]))

    [erro] = respostas
    assert isinstance(erro, CsErrorEnvelope)
    assert erro.error == ERR_MATCH_START == 241000201
    assert sala.state == ROOM_WAITING
    estados = [c[0xF] for op, c in _corpos(bia) if op == CsOp.CHANGE_ROOM_PROPERTY_OUT]
    assert estados == [ROOM_PLAYING, ROOM_WAITING]
    assert sala.members[9].ready is False
    assert historico.salvos == []


async def test_mapa_fora_do_catalogo_nao_inicia_a_partida() -> None:
    host = _HostFalso()
    handlers, lobby, rooms = _montagem(host, _Historico(), maps=_SemMapas())
    ana = _entra_no_lobby(lobby, 7, "Ana")
    bia = _entra_no_lobby(lobby, 9, "Bia")
    sala = _criar_sala(rooms, 7)
    rooms.join(sala.room_id, 9, "")
    await handlers.ready_game(bia, bytes([0]))

    respostas = await handlers.ready_game(ana, bytes([0]))

    assert host.iniciados == []
    assert [type(r) for r in respostas] == [CsErrorEnvelope]
    assert sala.state == ROOM_WAITING
    assert ana.outbox.qsize() >= 1


async def test_ultimo_a_sair_da_partida_grava_o_historico_e_devolve_a_sala_a_espera() -> None:
    host = _HostFalso()
    historico = _Historico()
    handlers, lobby, rooms = _montagem(host, historico)
    ana, bia, sala = await _partida(handlers, lobby, rooms)
    _corpos(ana)
    _corpos(bia)

    [saida] = await handlers.exit_play(ana, b"")
    assert isinstance(saida, CsExitPlayOut)
    assert historico.salvos == [] and sala.state == ROOM_PLAYING

    await handlers.exit_play(bia, b"")

    [gravado] = historico.salvos
    assert gravado.end_reason == "exit_play"
    assert gravado.map_file == "ONS-Treino"
    assert [(p.account_id, p.nickname, p.is_master) for p in gravado.players] == [
        (7, "Ana", True),
        (9, "Bia", False),
    ]
    # Métricas do jogo ficam nulas (sem bloco GameEnded); o tempo jogado vem do canal (D52).
    assert all(p.kills is None for p in gravado.players)
    assert all(p.played_seconds is not None for p in gravado.players)
    assert gravado.uuid is not None and len(gravado.uuid) == 36
    assert host.encerrados == [sala.room_id]
    assert sala.state == ROOM_WAITING
    assert all(not membro.ready for membro in sala.members.values())  # o dono também (D77)
    # O que o cliente do dono recebe ao fim: 402 dele com pronto zerado, não só o estado no domínio.
    pronto_do_dono = [
        corpo
        for op, corpo in _corpos(ana)
        if op == CsOp.READY_GAME_OUT and struct.unpack_from("<i", corpo)[0] == 7
    ]
    assert struct.unpack_from("<iB", pronto_do_dono[-1]) == (7, 0)


async def test_queda_do_servidor_depois_de_pronto_encerra_a_partida_com_server_exit() -> None:
    host = _HostFalso()
    historico = _Historico()
    handlers, lobby, rooms = _montagem(host, historico)
    _ana, _bia, sala = await _partida(handlers, lobby, rooms)
    assert host.on_exit is not None

    await host.on_exit()

    [gravado] = historico.salvos
    assert gravado.end_reason == "server_exit"
    assert sala.state == ROOM_WAITING


async def test_volta_a_propria_sala_depois_da_partida_recebe_312_314_317_so_quem_entrou() -> None:
    host = _HostFalso()
    handlers, lobby, rooms = _montagem(host, _Historico())
    ana, bia, sala = await _partida(handlers, lobby, rooms)
    await handlers.exit_play(ana, b"")
    await handlers.exit_play(bia, b"")
    _corpos(ana)
    _corpos(bia)

    respostas = await handlers.in_room(bia, struct.pack("<i16s", sala.room_id, b""))

    assert [type(r) for r in respostas] == [CsInRoomOut, CsRoomInfoOut, CsRoomPlayerInfoOut]
    assert _corpos(ana) == []  # o lobby já sabe que Bia está na sala: nada é difundido de novo


async def test_volta_com_a_partida_em_andamento_responde_so_a_quem_volta_e_nao_encerra() -> None:
    host = _HostFalso()
    historico = _Historico()
    handlers, lobby, rooms = _montagem(host, historico)
    ana, bia, sala = await _partida(handlers, lobby, rooms)
    await handlers.exit_play(ana, b"")  # Bia segue em jogo: a partida não acaba
    _corpos(ana)
    _corpos(bia)

    respostas = await handlers.in_room(ana, struct.pack("<i16s", sala.room_id, b""))

    assert [type(r) for r in respostas] == [CsInRoomOut, CsRoomInfoOut, CsRoomPlayerInfoOut]
    assert _corpos(bia) == []
    assert sala.state == ROOM_PLAYING
    assert historico.salvos == []


async def test_sair_da_ultima_pessoa_em_jogo_encerra_a_partida_sem_travar_a_sala() -> None:
    host = _HostFalso()
    historico = _Historico()
    handlers, lobby, rooms = _montagem(host, historico)
    ana, bia, sala = await _partida(handlers, lobby, rooms)
    await handlers.exit_play(ana, b"")

    await handlers.out_room(bia, b"")  # Bia sai sem mandar 500: era a última em jogo
    await asyncio.sleep(0)  # a gravação roda em tarefa

    [gravado] = historico.salvos
    assert gravado.end_reason == "exit_play"
    assert sala.state == ROOM_WAITING
    assert set(sala.members) == {7}


async def test_sala_que_esvazia_no_meio_da_partida_nao_grava_e_derruba_o_servidor() -> None:
    host = _HostFalso()
    historico = _Historico()
    handlers, lobby, rooms = _montagem(host, historico)
    ana, bia, sala = await _partida(handlers, lobby, rooms)

    await handlers.out_room(bia, b"")
    await handlers.out_room(ana, b"")
    await asyncio.sleep(0)

    assert rooms.get(sala.room_id) is None
    assert host.encerrados == [sala.room_id]
    assert historico.salvos == []


async def test_dono_so_fica_pronto_ao_iniciar_e_perde_o_pronto_ao_acabar() -> None:
    host = _HostFalso()
    handlers, lobby, rooms = _montagem(host, _Historico())
    ana = _entra_no_lobby(lobby, 7, "Ana")
    bia = _entra_no_lobby(lobby, 9, "Bia")
    sala = _criar_sala(rooms, 7)
    rooms.join(sala.room_id, 9, "")
    assert sala.members[7].ready is False  # Config e Mudar grupo do dono exigem não pronto

    await handlers.ready_game(bia, bytes([0]))
    await handlers.ready_game(ana, bytes([0]))
    assert sala.members[7].ready is True and sala.state == ROOM_PLAYING

    rooms.finish(sala.room_id)
    assert all(not membro.ready for membro in sala.members.values())


async def test_novo_dono_vindo_pronto_perde_o_pronto_na_espera_e_o_cliente_sabe() -> None:
    host = _HostFalso()
    handlers, lobby, rooms = _montagem(host, _Historico())
    _entra_no_lobby(lobby, 7, "Ana")
    bia = _entra_no_lobby(lobby, 9, "Bia")
    sala = _criar_sala(rooms, 7)
    rooms.join(sala.room_id, 9, "")
    await handlers.ready_game(bia, bytes([0]))
    _corpos(bia)

    handlers.leave(7)

    assert sala.master == 9 and sala.members[9].ready is False
    recebidos = _corpos(bia)
    assert recebidos[-1][0] == CsOp.READY_GAME_OUT
    assert struct.unpack_from("<iB", recebidos[-1][1], 0) == (9, 0)


async def test_586_responde_587_com_a_propria_chave_so_quem_esta_em_sala() -> None:
    host = _HostFalso()
    handlers, lobby, rooms = _montagem(host, _Historico())
    ana = _entra_no_lobby(lobby, 7, "Ana")

    assert await handlers.enter_hangar(ana, b"") == []  # fora de sala: sem resposta
    _criar_sala(rooms, 7)
    [resposta] = await handlers.enter_hangar(ana, b"")

    assert resposta.opcode == CsOp.ENTER_HANGAR_OUT
    assert resposta.pack() == struct.pack("<i", 7)


async def test_588_responde_589_com_a_propria_chave_e_posicao_de_sala() -> None:
    host = _HostFalso()
    handlers, lobby, rooms = _montagem(host, _Historico())
    ana = _entra_no_lobby(lobby, 7, "Ana")

    assert await handlers.leave_hangar(ana, b"") == []  # fora de sala: sem resposta
    _criar_sala(rooms, 7)
    [resposta] = await handlers.leave_hangar(ana, b"")

    assert isinstance(resposta, CsLeaveHangarOut)
    assert resposta.opcode == CsOp.LEAVE_HANGAR_OUT
    # i32 chave @0, u8 posição de sala (0x23) @4: o cliente só volta à sala com esses dois.
    assert resposta.pack() == struct.pack("<iB3x", 7, 0x23)


async def test_volta_sem_500_encerra_partida_e_devolve_sala_a_espera() -> None:
    host = _HostFalso()
    historico = _Historico()
    handlers, lobby, rooms = _montagem(host, historico)
    ana, bia, sala = await _partida(handlers, lobby, rooms)
    caio = _entra_no_lobby(lobby, 11, "Caio")  # fora de sala: recebe o 412 do lobby
    await handlers.exit_play(ana, b"")  # Ana sai pelo 500; Bia não manda nada (fim por tempo)
    _corpos(ana)
    _corpos(bia)
    _corpos(caio)

    respostas = await handlers.in_room(bia, struct.pack("<i16s", sala.room_id, b""))

    [gravado] = historico.salvos
    assert gravado.end_reason == "return_to_room"
    assert host.encerrados == [sala.room_id]
    assert sala.state == ROOM_WAITING
    assert [type(r) for r in respostas] == [CsInRoomOut, CsRoomInfoOut, CsRoomPlayerInfoOut]
    # Quem está na sala recebe 402 sem pronto de todos, e o lobby recebe 412 com o estado de espera.
    prontos = [
        struct.unpack_from("<iB", corpo) for op, corpo in _corpos(ana) if op == CsOp.READY_GAME_OUT
    ]
    ultimos = prontos[-2:]
    assert sorted(guid for guid, _ in ultimos) == [7, 9]
    assert all(pronto == 0 for _, pronto in ultimos)
    # 412 ao lobby com o estado de espera (byte @0xf, bit de estado na máscara @4).
    estados = [
        corpo
        for op, corpo in _corpos(caio)
        if op == CsOp.CHANGE_ROOM_PROPERTY_OUT and corpo[4] & ROOM_FLAG_STATE
    ]
    assert [corpo[0xF] for corpo in estados] == [ROOM_WAITING]
