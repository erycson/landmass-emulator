"""Comandos de GM (D193): codec de 250 e 251, regras de nível, aviso e expulsão no canal, e o nível
nos registros de 101, 151 e 317 (byte de `ucAccess` em @0x11 e @0x1a)."""

import pytest

from landmass_emu.domain.access import check_access_level, may_expel, may_notify
from landmass_emu.domain.lobby import Lobby
from landmass_emu.handlers.channel.gm import (
    ERR_NOT_ALLOWED,
    ERR_TARGET_OFFLINE,
    RESULT_EXPELLED,
    GmHandlers,
)
from landmass_emu.net.server import reply_body
from landmass_emu.net.session import Session
from landmass_emu.protocol.channel import (
    CsChannelPlayer,
    CsExpelPlayerIn,
    CsExpelPlayerOut,
    CsOp,
    CsRoomPlayer,
    CsSendCommandIn,
    CsSendCommandOut,
)
from landmass_emu.protocol.header import CHANNEL_NET_CODE
from landmass_emu.protocol.progression import PlayerRecord

POS_CHANNEL = 0x21


class _Auditoria:
    """Guarda as chamadas de `record`; satisfaz o que o handler usa de `EconomyAudit`."""

    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict[str, object]]] = []

    def record(self, session: Session, event: str, **fields: object) -> None:
        self.eventos.append((event, fields))


def _sessao(nick: str, fechamentos: list[str]) -> Session:
    return Session(peer=nick, closer=lambda: fechamentos.append(nick))


def _no_lobby(lobby: Lobby, guid: int, nick: str, access: int, fechamentos: list[str]) -> Session:
    sessao = _sessao(nick, fechamentos)
    lobby.join(guid, sessao, nick, 0, access)
    return sessao


def _montagem() -> tuple[GmHandlers, Lobby, _Auditoria, list[str]]:
    lobby = Lobby()
    auditoria = _Auditoria()
    return GmHandlers(lobby, auditoria), lobby, auditoria, []


# ---- Codec ---------------------------------------------------------------------------------------


def test_send_command_in_le_flag_e_texto() -> None:
    req = CsSendCommandIn.unpack(bytes([1, 3]) + b"oi!" + b"lixo")
    assert req == CsSendCommandIn(all_server=True, text=b"oi!")
    assert CsSendCommandIn.unpack(bytes([0, 0])) == CsSendCommandIn(all_server=False, text=b"")


def test_send_command_in_recusa_curto_e_len_acima_do_limite() -> None:
    with pytest.raises(ValueError):
        CsSendCommandIn.unpack(b"\x01")
    with pytest.raises(ValueError):
        CsSendCommandIn.unpack(bytes([1, 5]) + b"abc")  # len 5 e só 3 bytes de texto
    with pytest.raises(ValueError):
        CsSendCommandIn.unpack(bytes([1, 0x79]) + b"x" * 0x79)


def test_send_command_out_tem_len_texto_e_nul() -> None:
    assert CsSendCommandOut(b"aviso").pack() == bytes([5]) + b"aviso" + b"\x00"
    with pytest.raises(ValueError):
        CsSendCommandOut(b"x" * 0x79).pack()


def test_opcodes_250_e_251() -> None:
    assert CsOp.SEND_COMMAND == 250
    assert CsOp.SEND_COMMAND_OUT == 251
    assert CsOp.EXPEL_PLAYER == 700
    assert CsOp.EXPEL_PLAYER_OUT == 701


# ---- Regras de nível ----------------------------------------------------------------------------


def test_nivel_de_gm_e_a_partir_de_9() -> None:
    assert not may_notify(0)
    assert not may_notify(8)
    assert may_notify(9)
    assert may_notify(10)


def test_expulsao_so_de_quem_tem_nivel_menor() -> None:
    assert may_expel(9, 0)
    assert not may_expel(9, 9)  # entre pares, ninguém tira o outro
    assert not may_expel(9, 10)
    assert not may_expel(0, 0)  # jogador comum não expulsa


def test_nivel_fora_da_faixa_de_u8_e_recusado() -> None:
    check_access_level(0)
    check_access_level(255)
    with pytest.raises(ValueError):
        check_access_level(256)
    with pytest.raises(ValueError):
        check_access_level(-1)


# ---- Aviso (250 e 251) --------------------------------------------------------------------------


async def test_aviso_de_gm_vai_a_todo_o_lobby_incluindo_quem_mandou() -> None:
    gm, lobby, auditoria, fechamentos = _montagem()
    gm_sessao = _no_lobby(lobby, 1, "Admin", 9, fechamentos)
    jogador = _no_lobby(lobby, 2, "Bia", 0, fechamentos)

    replies = await gm.send_command(gm_sessao, bytes([1, 5]) + b"oi a)")

    assert replies == []
    esperado = reply_body(CsSendCommandOut(b"oi a)"), CHANNEL_NET_CODE)
    assert gm_sessao.outbox.get_nowait() == esperado
    assert jogador.outbox.get_nowait() == esperado
    assert auditoria.eventos == [
        ("gm_notice", {"all_server": True, "text": "oi a)"}),
    ]


async def test_aviso_de_jogador_sem_nivel_e_ignorado() -> None:
    gm, lobby, auditoria, fechamentos = _montagem()
    jogador = _no_lobby(lobby, 2, "Bia", 0, fechamentos)
    outro = _no_lobby(lobby, 3, "Ana", 0, fechamentos)

    assert await gm.send_command(jogador, bytes([0, 2]) + b"ok") == []

    assert jogador.outbox.empty()
    assert outro.outbox.empty()
    assert auditoria.eventos == []


async def test_aviso_fora_do_lobby_e_texto_vazio_nao_saem() -> None:
    gm, lobby, _auditoria, fechamentos = _montagem()
    fora = _sessao("Fora", fechamentos)
    assert await gm.send_command(fora, bytes([1, 2]) + b"oi") == []
    dentro = _no_lobby(lobby, 1, "Admin", 9, fechamentos)
    assert await gm.send_command(dentro, bytes([0, 0])) == []
    assert dentro.outbox.empty()


# ---- Expulsão (700 e 701) -----------------------------------------------------------------------


def _pedido(kind: int, nick: str) -> bytes:
    return CsExpelPlayerIn(kind, nick).pack()


async def test_gm_expulsa_jogador_do_canal_e_responde_quem_pediu() -> None:
    gm, lobby, auditoria, fechamentos = _montagem()
    admin = _no_lobby(lobby, 1, "Admin", 9, fechamentos)
    _no_lobby(lobby, 2, "Bia", 0, fechamentos)

    replies = await gm.expel_player(admin, _pedido(POS_CHANNEL, "Bia"))

    assert replies == [CsExpelPlayerOut(RESULT_EXPELLED)]
    assert fechamentos == ["Bia"]  # a queda passa pelo `disconnect` do canal
    assert auditoria.eventos[-1] == (
        "gm_expel",
        {
            "kind": POS_CHANNEL,
            "target_nickname": "Bia",
            "target_guid": 2,
            "result": RESULT_EXPELLED,
        },
    )


async def test_expulsao_de_alvo_fora_do_canal_responde_erro_sem_fechar_nada() -> None:
    gm, lobby, auditoria, fechamentos = _montagem()
    admin = _no_lobby(lobby, 1, "Admin", 9, fechamentos)

    replies = await gm.expel_player(admin, _pedido(POS_CHANNEL, "Ninguem"))

    assert replies == [CsExpelPlayerOut(ERR_TARGET_OFFLINE)]
    assert fechamentos == []
    assert auditoria.eventos[-1][1]["result"] == ERR_TARGET_OFFLINE


async def test_gm_nao_expulsa_nivel_igual_ou_maior() -> None:
    gm, lobby, _auditoria, fechamentos = _montagem()
    admin = _no_lobby(lobby, 1, "Admin", 9, fechamentos)
    _no_lobby(lobby, 2, "Outro", 9, fechamentos)
    _no_lobby(lobby, 3, "Chefe", 10, fechamentos)

    assert await gm.expel_player(admin, _pedido(POS_CHANNEL, "Outro")) == [
        CsExpelPlayerOut(ERR_NOT_ALLOWED)
    ]
    assert await gm.expel_player(admin, _pedido(POS_CHANNEL, "Chefe")) == [
        CsExpelPlayerOut(ERR_NOT_ALLOWED)
    ]
    assert fechamentos == []


async def test_expulsao_de_jogador_sem_nivel_e_ignorada() -> None:
    gm, lobby, _auditoria, fechamentos = _montagem()
    jogador = _no_lobby(lobby, 1, "Bia", 0, fechamentos)
    _no_lobby(lobby, 2, "Ana", 0, fechamentos)

    assert await gm.expel_player(jogador, _pedido(POS_CHANNEL, "Ana")) == []
    assert fechamentos == []


async def test_tipo_de_expulsao_desconhecido_e_ignorado() -> None:
    gm, lobby, _auditoria, fechamentos = _montagem()
    admin = _no_lobby(lobby, 1, "Admin", 9, fechamentos)
    _no_lobby(lobby, 2, "Bia", 0, fechamentos)

    assert await gm.expel_player(admin, _pedido(0x55, "Bia")) == []
    assert fechamentos == []


# ---- Nível nos registros do canal ---------------------------------------------------------------


def test_nivel_vai_no_byte_0x1a_do_registro_de_151_e_de_317() -> None:
    assert CsChannelPlayer(client_guid=7, nick="Bia", access=9).pack()[0x1A] == 9
    room = CsRoomPlayer(client_guid=7, slot=0, ready=False, morats=0, nick="Bia", access=10)
    assert room.pack()[0x1A] == 10


def test_nivel_vai_no_byte_0x11_do_registro_de_101() -> None:
    assert PlayerRecord(access=9).pack(7)[0x11] == 9
    assert PlayerRecord().pack(7)[0x11] == 0
