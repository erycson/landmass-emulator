"""Salas no Channel Server por TCP, com dois ou três clientes (marco 3)."""

import struct
from pathlib import Path

from test_channel_server import (
    TOKEN_ANA,
    TOKEN_BIA,
    Client,
    _chave_de_sessao,
    _chave_payload,
    _connect,
    _entra_no_canal,
    _settings,
)

from landmass_emu.app import game_servers, open_accounts
from landmass_emu.domain.account import hash_token
from landmass_emu.protocol.channel import CsOp
from landmass_emu.protocol.header import CHANNEL_NET_CODE
from landmass_emu.protocol.message import cfield, cstr

TOKEN_CRIS = "00112233445566778899aabbccddeeff"
SENHA = "segredo"
ERRO_NOME_CURTO = 211000202


def _payload_criar(nome: str, senha: str = "") -> bytes:
    """CREATE_ROOM (301): `char name[32]`, `char password[16]`, seis i32 e u16 (74 bytes)."""
    return struct.pack("<32s16s6iH", cfield(nome, 32), cfield(senha, 16), 0, 1, 1, 4, 1, 10, 10)


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
    await c.send(CsOp.IN_CHANNEL)
    await c.expect(CsOp.CHANNEL_PLAYER_INFO_OUT)
    lista = await c.expect(CsOp.CHANNEL_ROOM_INFO_OUT)
    assert struct.unpack_from("<i", await c.expect(CsOp.IN_CHANNEL_OUT), 0) == (guid,)
    for outro in no_lobby:
        assert struct.unpack_from("<i", await outro.expect(CsOp.IN_CHANNEL_OUT), 0) == (guid,)
    return lista


async def _cria_sala(a: Client, b: Client, nome: str, senha: str = "") -> int:
    """A cria a sala. B, no lobby, recebe o 302 e o 312 do canal; A recebe também 314 e 317."""
    await a.send(CsOp.CREATE_ROOM, _payload_criar(nome, senha))
    criada = await a.expect(CsOp.CREATE_ROOM_OUT)
    assert await b.expect(CsOp.CREATE_ROOM_OUT) == criada
    await a.expect(CsOp.IN_ROOM_OUT)
    await b.expect(CsOp.IN_ROOM_OUT)
    await a.expect(CsOp.ROOM_INFO_OUT)
    await a.expect(CsOp.ROOM_PLAYER_INFO_OUT)
    return struct.unpack_from("<i", criada, 0)[0]


async def test_dois_clientes_na_mesma_sala_ficam_prontos_e_recebem_o_inicio(
    tmp_path: Path,
) -> None:
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
            assert cstr(criada[0x10:0x30]) == "Sala Azul"
            assert struct.unpack_from("<i", criada, 0x4C) == (ana.id,)
            for x in (a, b):
                assert struct.unpack("<iii", await x.expect(CsOp.IN_ROOM_OUT)) == (sala, ana.id, 0)
            # Só A recebe o detalhe da sala (314) e a lista de jogadores (317).
            assert struct.unpack_from("<i", await a.expect(CsOp.ROOM_INFO_OUT), 0x0C) == (sala,)
            assert _jogadores(await a.expect(CsOp.ROOM_PLAYER_INFO_OUT)) == {ana.id: (0, True)}

            # B entra: o 312 vai ao canal; 314 e 317 só a B, que vê os dois nos slots.
            await b.send(CsOp.IN_ROOM, _payload_entrar(sala))
            for x in (a, b):
                assert struct.unpack("<iii", await x.expect(CsOp.IN_ROOM_OUT)) == (sala, bia.id, 1)
            await b.expect(CsOp.ROOM_INFO_OUT)
            assert _jogadores(await b.expect(CsOp.ROOM_PLAYER_INFO_OUT)) == {
                ana.id: (0, True),
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
                assert estado[0xF] == 2  # ROOM_PLAYING
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
            for x in (a, b):
                await x.expect(CsOp.IN_ROOM_OUT)
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

            # C entra depois: o 141 já traz a sala, com o nome e o bit de senha (@0x30).
            lista = await _entra_com_outros(c, chave_cris, cris.id, a, b)
            assert struct.unpack_from("<H", lista, 0) == (1,)
            assert struct.unpack_from("<i", lista, 2) == (sala,)
            assert cstr(lista[2 + 0x10 : 2 + 0x30]) == "Sala Azul"
            assert lista[2 + 0x30] == 1

            # Senha errada: só B recebe a recusa (312 com código 1701 em i16); ninguém mais.
            await b.send(CsOp.IN_ROOM, _payload_entrar(sala, "errada"))
            recusa = await b.expect(CsOp.IN_ROOM_OUT)
            assert len(recusa) == 0x12
            assert struct.unpack_from("<h", recusa, 0) == (1701,)
            await a.assert_silencio()
            await c.assert_silencio()
            await b.assert_silencio()

            # Com a senha certa, entra: 312 ao canal; 314 e 317 só a B.
            await b.send(CsOp.IN_ROOM, _payload_entrar(sala, SENHA))
            for x in (a, b, c):
                assert struct.unpack("<iii", await x.expect(CsOp.IN_ROOM_OUT)) == (sala, bia.id, 1)
            await b.expect(CsOp.ROOM_INFO_OUT)
            assert len(_jogadores(await b.expect(CsOp.ROOM_PLAYER_INFO_OUT))) == 2
