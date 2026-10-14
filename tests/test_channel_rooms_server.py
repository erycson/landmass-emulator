"""Salas no Channel Server por TCP, com dois ou três clientes (marco 3)."""

import struct
from collections.abc import Callable
from pathlib import Path

from test_channel_server import (
    TOKEN_ANA,
    TOKEN_BIA,
    Client,
    _chave_de_sessao,
    _chave_payload,
    _connect,
    _entra_no_canal,
    _saldos_do_login,
    _settings,
)

from landmass_emu.app import game_servers, open_accounts
from landmass_emu.domain.account import hash_token
from landmass_emu.protocol.channel import NICK_SIZE, ROOM_FLAG_LIMIT_PLAYER, CsOp
from landmass_emu.protocol.header import CHANNEL_NET_CODE
from landmass_emu.protocol.message import cfield, cstr

TOKEN_CRIS = "00112233445566778899aabbccddeeff"
SENHA = "segredo"
ERRO_NOME_CURTO = 211000202


def _payload_criar(nome: str, senha: str = "", grupos: int = 1) -> bytes:
    """CREATE_ROOM (301), layout de `CsCreateRoomIn`. `grupos` é o team_count."""
    return struct.pack(
        "<H51s13sBBBBBxH", 1, cfield(nome, 51), cfield(senha, 13), 0, 1, grupos, 4, 10, 10
    )


def _payload_entrar(sala: int, senha: str = "") -> bytes:
    """IN_ROOM (311): `i32 room_id` e `char password[16]` (20 bytes)."""
    return struct.pack("<i16s", sala, cfield(senha, 16))


def _jogadores(body: bytes) -> dict[int, tuple[int, bool]]:
    """Corpo do 317: `u8` contagem e entradas de 48 bytes. Devolve guid -> (slot, pronto)."""
    quantos = body[0]
    assert len(body) == 1 + 48 * quantos
    saida: dict[int, tuple[int, bool]] = {}
    for i in range(quantos):
        entrada = body[1 + 48 * i : 1 + 48 * (i + 1)]
        (guid,) = struct.unpack_from("<i", entrada, 0)
        saida[guid] = (entrada[0x28], bool(entrada[0x29]))
    return saida


async def _entra_com_outros(c: Client, chave: str, guid: int, *no_lobby: Client) -> bytes:
    """Entra no canal com outros já lá: eles recebem a entrada (123). Devolve a lista (141)."""
    await c.send(CsOp.IN_CHANNEL_SERVER, _chave_payload(chave))
    await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
    await c.expect(CsOp.CHANNEL_INFO_OUT)
    await _saldos_do_login(c)
    await c.send(CsOp.IN_CHANNEL)
    await c.expect(CsOp.CHANNEL_PLAYER_INFO_OUT)
    lista = await c.expect(CsOp.CHANNEL_ROOM_INFO_OUT)
    assert struct.unpack_from("<i", await c.expect(CsOp.IN_CHANNEL_OUT), 0) == (guid,)
    for outro in no_lobby:
        assert struct.unpack_from("<i", await outro.expect(CsOp.IN_CHANNEL_OUT), 0) == (guid,)
    return lista


async def _cria_sala(a: Client, b: Client, nome: str, senha: str = "", grupos: int = 1) -> int:
    """A cria a sala. B, no lobby, recebe o 302 e o 312 do canal; A recebe também 314 e 317."""
    await a.send(CsOp.CREATE_ROOM, _payload_criar(nome, senha, grupos))
    criada = await a.expect(CsOp.CREATE_ROOM_OUT)
    assert await b.expect(CsOp.CREATE_ROOM_OUT) == criada
    await a.expect(CsOp.IN_ROOM_OUT)
    await b.expect(CsOp.IN_ROOM_OUT)
    await a.expect(CsOp.ROOM_INFO_OUT)
    await a.expect(CsOp.ROOM_PLAYER_INFO_OUT)
    return struct.unpack_from("<i", criada, 0)[0]


async def test_dois_clientes_na_mesma_sala_ficam_prontos_e_recebem_o_inicio(
    tmp_path: Path, wdb_de_teste: Callable[[], Path]
) -> None:
    wdb_de_teste()  # o início consulta o mapa em landmass.wdb (client_dir)
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana = await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))
        bia = await accounts.create("bia", "Bia", hash_token(TOKEN_BIA))

    async with game_servers(settings) as (msg, ch):
        chave_ana = await _chave_de_sessao(msg, TOKEN_ANA)
        chave_bia = await _chave_de_sessao(msg, TOKEN_BIA)

        async with (
            _connect(ch, CHANNEL_NET_CODE) as a,
            _connect(ch, CHANNEL_NET_CODE) as b,
        ):
            await _entra_no_canal(a, chave_ana, ana.id)
            await _entra_com_outros(b, chave_bia, bia.id, a)

            # A cria: o 302 chega aos dois, então B vê a sala; o 312 põe A no slot 0.
            await a.send(CsOp.CREATE_ROOM, _payload_criar("Sala Azul"))
            criada = await a.expect(CsOp.CREATE_ROOM_OUT)
            assert await b.expect(CsOp.CREATE_ROOM_OUT) == criada
            sala = struct.unpack_from("<i", criada, 0)[0]
            assert cstr(criada[0x04:0x37]) == "Sala Azul"
            assert struct.unpack_from("<i", criada, 0x4C) == (ana.id,)
            assert criada[0x38] == 0  # ROOM_WAITING (RS_WAITING = 0): o dono vê a sala em espera
            for x in (a, b):
                assert struct.unpack("<iii", await x.expect(CsOp.IN_ROOM_OUT)) == (sala, ana.id, 0)
            # Só A recebe o detalhe da sala (314) e a lista de jogadores (317).
            assert struct.unpack_from("<i", await a.expect(CsOp.ROOM_INFO_OUT), 0x0C) == (sala,)
            # Dono sem pronto na espera (D77).
            assert _jogadores(await a.expect(CsOp.ROOM_PLAYER_INFO_OUT)) == {ana.id: (0, False)}

            # B entra: A, que já está na sala, recebe só o 549 (quem chegou); B recebe o 312.
            # 314 e 317 só a B, que vê os dois nos slots.
            await b.send(CsOp.IN_ROOM, _payload_entrar(sala))
            assert struct.unpack("<iii", await b.expect(CsOp.IN_ROOM_OUT)) == (sala, bia.id, 1)
            entrada = await a.expect(CsOp.ROOM_ENTRY_OUT)
            assert struct.unpack_from("<i", entrada, 0) == (bia.id,)
            assert entrada[0x28] == 1  # slot de B
            await b.expect(CsOp.ROOM_INFO_OUT)
            assert _jogadores(await b.expect(CsOp.ROOM_PLAYER_INFO_OUT)) == {
                ana.id: (0, False),
                bia.id: (1, False),
            }
            await a.assert_silencio()

            # B marca pronto: 402 aos dois. A, dono, inicia: 412 ao canal e 403 à sala.
            await b.send(CsOp.READY_GAME, bytes([0]))
            for x in (a, b):
                pronto = await x.expect(CsOp.READY_GAME_OUT)
                assert struct.unpack_from("<iB", pronto, 0) == (bia.id, 1)
            await a.send(CsOp.READY_GAME, bytes([0]))
            for x in (a, b):
                estado = await x.expect(CsOp.CHANGE_ROOM_PROPERTY_OUT)
                assert struct.unpack_from("<i", estado, 0) == (sala,)
                assert estado[0xF] == 1  # ROOM_PLAYING (RS_PLAYING = 1)
                dono = await x.expect(CsOp.READY_GAME_OUT)  # dono pronto dispara a contagem (D77)
                assert struct.unpack_from("<iB", dono, 0) == (ana.id, 1)
                inicio = await x.expect(CsOp.START_GAME_OUT)
                assert cstr(inicio[:16]) == "127.0.0.1"
                assert struct.unpack_from("<H", inicio, 16) == (7777,)


async def test_sair_passa_o_dono_e_a_sala_vazia_some_da_lista(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana = await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))
        bia = await accounts.create("bia", "Bia", hash_token(TOKEN_BIA))

    async with game_servers(settings) as (msg, ch):
        chave_ana = await _chave_de_sessao(msg, TOKEN_ANA)
        chave_bia = await _chave_de_sessao(msg, TOKEN_BIA)

        async with (
            _connect(ch, CHANNEL_NET_CODE) as a,
            _connect(ch, CHANNEL_NET_CODE) as b,
        ):
            await _entra_no_canal(a, chave_ana, ana.id)
            await _entra_com_outros(b, chave_bia, bia.id, a)

            # Nome curto: erro só ao criador, com o opcode 302 no envelope.
            await a.send(CsOp.CREATE_ROOM, _payload_criar("ab"))
            erro = await a.expect(CsOp.ERROR)
            assert len(erro) == 8
            assert struct.unpack_from("<H", erro, 0) == (CsOp.CREATE_ROOM_OUT,)
            assert struct.unpack_from("<i", erro, 4) == (ERRO_NOME_CURTO,)
            await b.assert_silencio()

            sala = await _cria_sala(a, b, "Sala Azul")
            await b.send(CsOp.IN_ROOM, _payload_entrar(sala))
            await b.expect(CsOp.IN_ROOM_OUT)
            await a.expect(CsOp.ROOM_ENTRY_OUT)
            await b.expect(CsOp.ROOM_INFO_OUT)
            await b.expect(CsOp.ROOM_PLAYER_INFO_OUT)

            # A sai: 322 ao canal; B vira o dono (332).
            await a.send(CsOp.OUT_ROOM)
            for x in (a, b):
                assert struct.unpack("<ii", await x.expect(CsOp.OUT_ROOM_OUT)) == (sala, ana.id)
                assert struct.unpack("<ii", await x.expect(CsOp.CHANGE_ROOM_MASTER_OUT)) == (
                    sala,
                    bia.id,
                )

            # Bia, agora dona, perde o pronto na espera: 402 só para a sala (D77).
            assert struct.unpack_from("<iB", await b.expect(CsOp.READY_GAME_OUT), 0) == (bia.id, 0)

            # B sai e a sala esvazia: 322 e depois 342 (remoção) chegam a todo o canal.
            await b.send(CsOp.OUT_ROOM)
            for x in (a, b):
                assert struct.unpack("<ii", await x.expect(CsOp.OUT_ROOM_OUT)) == (sala, bia.id)
                assert struct.unpack("<i", await x.expect(CsOp.REMOVE_ROOM_OUT)) == (sala,)


async def test_pedido_545_responde_so_a_quem_pediu_com_as_salas_existentes(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana = await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))
        bia = await accounts.create("bia", "Bia", hash_token(TOKEN_BIA))

    async with game_servers(settings) as (msg, ch):
        chave_ana = await _chave_de_sessao(msg, TOKEN_ANA)
        chave_bia = await _chave_de_sessao(msg, TOKEN_BIA)

        async with (
            _connect(ch, CHANNEL_NET_CODE) as a,
            _connect(ch, CHANNEL_NET_CODE) as b,
        ):
            await _entra_no_canal(a, chave_ana, ana.id)
            await _entra_com_outros(b, chave_bia, bia.id, a)
            sala = await _cria_sala(a, b, "Sala Azul")

            # B pede a sala criada e uma guid inexistente: a 547 traz só a sala; A não recebe nada.
            pedido = bytearray(44)
            pedido[4] = 2
            struct.pack_into("<ii", pedido, 8, sala, 999_999)
            await b.send(CsOp.REFRESH_ROOM_LIST, bytes(pedido))
            resposta = await b.expect(CsOp.REFRESH_ROOM_LIST_OUT)
            assert resposta[0] == 1
            assert struct.unpack_from("<i", resposta, 4) == (sala,)
            await a.assert_silencio()


async def test_senha_errada_e_recusada_e_quem_entra_no_lobby_ve_a_sala(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana = await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))
        bia = await accounts.create("bia", "Bia", hash_token(TOKEN_BIA))
        cris = await accounts.create("cris", "Cris", hash_token(TOKEN_CRIS))

    async with game_servers(settings) as (msg, ch):
        chave_ana = await _chave_de_sessao(msg, TOKEN_ANA)
        chave_bia = await _chave_de_sessao(msg, TOKEN_BIA)
        chave_cris = await _chave_de_sessao(msg, TOKEN_CRIS)

        async with (
            _connect(ch, CHANNEL_NET_CODE) as a,
            _connect(ch, CHANNEL_NET_CODE) as b,
            _connect(ch, CHANNEL_NET_CODE) as c,
        ):
            await _entra_no_canal(a, chave_ana, ana.id)
            await _entra_com_outros(b, chave_bia, bia.id, a)

            sala = await _cria_sala(a, b, "Sala Azul", SENHA)

            # C entra depois: o 141 já traz a sala, com o nome (@0x04) e o bit de senha (@0x37).
            lista = await _entra_com_outros(c, chave_cris, cris.id, a, b)
            assert struct.unpack_from("<H", lista, 0) == (1,)
            assert struct.unpack_from("<i", lista, 2) == (sala,)
            assert cstr(lista[2 + 0x04 : 2 + 0x37]) == "Sala Azul"
            assert lista[2 + 0x37] == 1

            # Senha errada: só B recebe a recusa (312 com código 1701 em i16); ninguém mais.
            await b.send(CsOp.IN_ROOM, _payload_entrar(sala, "errada"))
            recusa = await b.expect(CsOp.IN_ROOM_OUT)
            assert len(recusa) == 0x12
            assert struct.unpack_from("<h", recusa, 0) == (1701,)
            await a.assert_silencio()
            await c.assert_silencio()
            await b.assert_silencio()

            # Com a senha certa, entra: A (já na sala) recebe 549; B e C, 312; 314 e 317 só a B.
            await b.send(CsOp.IN_ROOM, _payload_entrar(sala, SENHA))
            for x in (b, c):
                assert struct.unpack("<iii", await x.expect(CsOp.IN_ROOM_OUT)) == (sala, bia.id, 1)
            assert struct.unpack_from("<i", await a.expect(CsOp.ROOM_ENTRY_OUT), 0) == (bia.id,)
            await b.expect(CsOp.ROOM_INFO_OUT)
            assert len(_jogadores(await b.expect(CsOp.ROOM_PLAYER_INFO_OUT))) == 2


async def test_dono_configura_e_entrante_muda_de_grupo_com_sala_em_espera(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana = await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))
        bia = await accounts.create("bia", "Bia", hash_token(TOKEN_BIA))

    async with game_servers(settings) as (msg, ch):
        chave_ana = await _chave_de_sessao(msg, TOKEN_ANA)
        chave_bia = await _chave_de_sessao(msg, TOKEN_BIA)

        async with (
            _connect(ch, CHANNEL_NET_CODE) as a,
            _connect(ch, CHANNEL_NET_CODE) as b,
        ):
            await _entra_no_canal(a, chave_ana, ana.id)
            await _entra_com_outros(b, chave_bia, bia.id, a)
            # Dois grupos: slots pares no grupo 0 e ímpares no grupo 1. A (dono) é o slot 0; B, o 1.
            sala = await _cria_sala(a, b, "Sala Azul", grupos=2)
            await b.send(CsOp.IN_ROOM, _payload_entrar(sala))
            await b.expect(CsOp.IN_ROOM_OUT)
            await a.expect(CsOp.ROOM_ENTRY_OUT)
            await b.expect(CsOp.ROOM_INFO_OUT)
            await b.expect(CsOp.ROOM_PLAYER_INFO_OUT)

            # Dono em sala de espera: 411 passa e 412 chega aos dois com o máximo novo (6).
            pedido = struct.pack("<BxHBBBBH", ROOM_FLAG_LIMIT_PLAYER, 0, 0, 0, 6, 0, 0)
            await a.send(CsOp.CHANGE_ROOM_PROPERTY, pedido)
            for x in (a, b):
                resposta = await x.expect(CsOp.CHANGE_ROOM_PROPERTY_OUT)
                assert struct.unpack_from("<i", resposta, 0) == (sala,)
                assert resposta[0xA] == 6

            # B, no grupo 1, pede o grupo 0: o primeiro livre é o slot 2 (o 0 é de A).
            await b.send(CsOp.CHANGE_ROOM_SLOT, bytes([0]))
            for x in (a, b):
                assert struct.unpack_from("<iB", await x.expect(CsOp.CHANGE_ROOM_SLOT_OUT), 0) == (
                    bia.id,
                    2,
                )


async def test_ficha_de_quem_esta_no_lobby_volta_com_o_nick(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana = await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))
        bia = await accounts.create("bia", "Bia", hash_token(TOKEN_BIA))

    async with game_servers(settings) as (msg, ch):
        chave_ana = await _chave_de_sessao(msg, TOKEN_ANA)
        chave_bia = await _chave_de_sessao(msg, TOKEN_BIA)

        async with (
            _connect(ch, CHANNEL_NET_CODE) as a,
            _connect(ch, CHANNEL_NET_CODE) as b,
        ):
            await _entra_no_canal(a, chave_ana, ana.id)
            await _entra_com_outros(b, chave_bia, bia.id, a)

            # B clica no nick de A: a ficha (543) volta com o nick; as estatísticas saem zero.
            await b.send(CsOp.PLAYER_DETAIL_IN, cfield("Ana", NICK_SIZE))
            ficha = await b.expect(CsOp.PLAYER_DETAIL_OUT)
            assert cstr(ficha[:20]) == "Ana"
            assert ficha[0x14:0x30] == bytes(0x1C)
            await a.assert_silencio()
