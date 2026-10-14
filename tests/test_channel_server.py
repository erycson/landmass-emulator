import asyncio
import contextlib
import struct
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from landmass_emu.app import game_servers, open_accounts, open_database
from landmass_emu.db.options import KeyBindDefaults, MouseDefaults
from landmass_emu.db.progression import SqlProgressionRepository
from landmass_emu.domain.account import hash_token
from landmass_emu.domain.progression import Grant
from landmass_emu.net.framing import encode_frame, read_frame
from landmass_emu.net.server import Service
from landmass_emu.protocol.channel import CsHeartbeat, CsOp
from landmass_emu.protocol.header import (
    CHANNEL_NET_CODE,
    MESSAGE_NET_CODE,
    pack_header,
    unpack_header,
)
from landmass_emu.protocol.message import LmRegisterInfo, MsLoginIn, MsOp, cstr
from landmass_emu.protocol.notice import NOTICE_OPCODE
from landmass_emu.protocol.progression import CsProgressionOp
from landmass_emu.settings import Settings
from landmass_emu.shutdown import Shutdown

TOKEN_ANA = "0123456789abcdef0123456789abcdef"
TOKEN_BIA = "fedcba9876543210fedcba9876543210"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/landmass.db",
        bind_host="127.0.0.1",
        message_port=0,
        channel_port=0,
        client_dir=tmp_path,
    )


def _chave_payload(chave: str) -> bytes:
    """CS_IN_CHANNEL_SERVER_IN: session_key em char[33]."""
    return chave.encode("ascii").ljust(33, b"\0")


async def _register_body(msg: asyncio.Server, token: str) -> bytes:
    """Login (100) e registro (110) no Message. Devolve o corpo do 111."""
    async with _connect(msg, MESSAGE_NET_CODE) as m:
        await m.send(MsOp.LOGIN, MsLoginIn(login_num=token).pack())
        assert struct.unpack_from("<i", await m.expect(MsOp.LOGIN_OUT), 4) == (0,)
        await m.send(MsOp.REGISTER)
        return await m.expect(MsOp.REGISTER_OUT)


async def _chave_de_sessao(msg: asyncio.Server, token: str) -> str:
    """Login (100) e registro (110) no Message. A chave vem no 111, `char[33]` @0x25."""
    body = await _register_body(msg, token)
    chave = cstr(body[0x25:0x46])
    assert len(chave) == 32
    return chave


class Client:
    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, net_code: int
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.net_code = net_code

    async def send(self, opcode: int, payload: bytes = b"") -> None:
        self.writer.write(encode_frame(pack_header(opcode, self.net_code) + payload))
        await self.writer.drain()

    async def recv(self) -> tuple[int, bytes]:
        async with asyncio.timeout(2):
            body = await read_frame(self.reader)
        assert body is not None
        header, payload = unpack_header(body)
        return header.opcode, payload

    async def expect(self, opcode: int) -> bytes:
        op, body = await self.recv()
        assert op == opcode, f"esperado opcode {opcode}, veio {op}"
        return body

    async def assert_silencio(self) -> None:
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.3):
                await read_frame(self.reader)


@asynccontextmanager
async def _connect(server: asyncio.Server, net_code: int) -> AsyncIterator[Client]:
    port = server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        yield Client(reader, writer, net_code)
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()


async def _saldos_do_login(c: Client) -> None:
    """Depois do 111, o login envia os saldos: 900 (Cash) e 902 (LD). Conta nova: zeros."""
    assert await c.expect(CsProgressionOp.CHARGE_CASH_OUT) == bytes(4)
    assert await c.expect(CsProgressionOp.CHARGE_POINT_OUT) == bytes(4)


async def _entra_no_canal(c: Client, chave: str, guid: int) -> None:
    """100 → 101/111/900/902, depois 120 → 151/141/121. Confere o id nos offsets do cliente."""
    await c.send(CsOp.IN_CHANNEL_SERVER, _chave_payload(chave))
    body = await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
    assert struct.unpack_from("<i", body, 0x90) == (guid,)
    assert struct.unpack_from("<i", body, 0xA0) == (guid,)
    assert struct.unpack_from("<i", body, 0xA8) == (0,)
    assert await c.expect(CsOp.CHANNEL_INFO_OUT) == b"\x01\x00"
    await _saldos_do_login(c)
    await c.send(CsOp.IN_CHANNEL)
    await c.expect(CsOp.CHANNEL_PLAYER_INFO_OUT)
    await c.expect(CsOp.CHANNEL_ROOM_INFO_OUT)
    body = await c.expect(CsOp.IN_CHANNEL_OUT)
    assert struct.unpack_from("<i", body, 0) == (guid,)


async def test_dois_clientes_se_veem_no_lobby(tmp_path: Path) -> None:
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

            # B: a lista já traz A; A recebe o broadcast de B.
            await b.send(CsOp.IN_CHANNEL_SERVER, _chave_payload(chave_bia))
            await b.expect(CsOp.IN_CHANNEL_SERVER_OUT)
            await b.expect(CsOp.CHANNEL_INFO_OUT)
            await _saldos_do_login(b)
            await b.send(CsOp.IN_CHANNEL)
            lista = await b.expect(CsOp.CHANNEL_PLAYER_INFO_OUT)
            assert lista[0:2] == b"\x02\x00"  # A e B: a 151 inclui quem está pedindo
            assert struct.unpack_from("<i", lista, 2) == (ana.id,)
            assert struct.unpack_from("<i", lista, 42) == (bia.id,)
            await b.expect(CsOp.CHANNEL_ROOM_INFO_OUT)
            assert struct.unpack_from("<i", await b.expect(CsOp.IN_CHANNEL_OUT), 0) == (bia.id,)
            assert struct.unpack_from("<i", await a.expect(CsOp.IN_CHANNEL_OUT), 0) == (bia.id,)

            # Chat de B chega a A e a B (remetente incluído).
            await b.send(CsOp.SEND_MESSAGE, bytes([0, 2]) + b"oi")
            for c in (a, b):
                body = await c.expect(CsOp.SEND_MESSAGE_OUT)
                assert struct.unpack_from("<i", body, 0) == (bia.id,)
                assert body[4] == 0 and body[5] == 2 and body[8:10] == b"oi"

            # Chat de A, com tipo 1.
            await a.send(CsOp.SEND_MESSAGE, bytes([1, 3]) + b"ola")
            for c in (a, b):
                body = await c.expect(CsOp.SEND_MESSAGE_OUT)
                assert struct.unpack_from("<i", body, 0) == (ana.id,)
                assert body[4] == 1 and body[8:11] == b"ola"

            # Saída voluntária: B recebe a própria saída; A recebe a de B.
            await b.send(CsOp.OUT_CHANNEL)
            for c in (a, b):
                body = await c.expect(CsOp.OUT_CHANNEL_OUT)
                assert struct.unpack_from("<i", body, 0) == (bia.id,)

            # B volta ao lobby e cai sem sair: a queda da conexão gera a saída para A.
            await b.send(CsOp.IN_CHANNEL)
            await b.expect(CsOp.CHANNEL_PLAYER_INFO_OUT)
            await b.expect(CsOp.CHANNEL_ROOM_INFO_OUT)
            await b.expect(CsOp.IN_CHANNEL_OUT)
            await a.expect(CsOp.IN_CHANNEL_OUT)
            b.writer.close()
            body = await a.expect(CsOp.OUT_CHANNEL_OUT)
            assert struct.unpack_from("<i", body, 0) == (bia.id,)


async def test_pedidos_fora_de_ordem_e_opcodes_desconhecidos_nao_derrubam(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))

    async with game_servers(settings) as (msg, ch):
        chave = await _chave_de_sessao(msg, TOKEN_ANA)
        async with _connect(ch, CHANNEL_NET_CODE) as c:
            await c.send(182, b"\x01\x02")  # opcode sem handler
            await c.send(CsOp.IN_CHANNEL)  # sem login: ignorado
            await c.send(CsOp.SEND_MESSAGE, bytes([0, 1]) + b"x")  # sem login: ignorado
            await c.send(CsOp.HEARTBEAT)  # cliente: sem resposta
            await c.assert_silencio()

            await c.send(CsOp.IN_CHANNEL_SERVER, _chave_payload("f" * 32))
            body = await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
            assert struct.unpack_from("<i", body, 0xA8) == (-160,)
            await c.send(CsOp.IN_CHANNEL_SERVER, b"curto")  # payload inválido: ignorado
            await c.send(182, b"")
            await c.send(CsOp.IN_CHANNEL_SERVER, _chave_payload(chave))
            await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
            await c.expect(CsOp.CHANNEL_INFO_OUT)
            await _saldos_do_login(c)


async def test_chave_zerada_ou_inventada_e_recusada(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))

    async with game_servers(settings) as (msg, ch):
        await _chave_de_sessao(msg, TOKEN_ANA)  # há uma chave válida; as recusadas não são ela
        async with _connect(ch, CHANNEL_NET_CODE) as c:
            for payload in (bytes(33), _chave_payload("0" * 32), _chave_payload("f" * 32)):
                await c.send(CsOp.IN_CHANNEL_SERVER, payload)
                body = await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
                assert struct.unpack_from("<i", body, 0xA8) == (-160,)
            # Recusado não entra no lobby: o pedido 120 sem login é ignorado.
            await c.send(CsOp.IN_CHANNEL)
            await c.assert_silencio()


async def test_chave_reemitida_invalida_a_antiga(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))

    async with game_servers(settings) as (msg, ch):
        antiga = await _chave_de_sessao(msg, TOKEN_ANA)
        nova = await _chave_de_sessao(msg, TOKEN_ANA)
        assert nova != antiga
        async with _connect(ch, CHANNEL_NET_CODE) as c:
            await c.send(CsOp.IN_CHANNEL_SERVER, _chave_payload(antiga))
            body = await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
            assert struct.unpack_from("<i", body, 0xA8) == (-160,)
            await c.send(CsOp.IN_CHANNEL_SERVER, _chave_payload(nova))
            body = await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
            assert struct.unpack_from("<i", body, 0xA8) == (0,)


# 37 valores distintos: cada byte identifica a sua posição em LM_REGISTER_INFO.
OPCOES = bytes(range(1, 38))


async def test_opcoes_do_canal_voltam_no_111_do_proximo_login(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))

    async with game_servers(settings) as (msg, ch):
        corpo = await _register_body(msg, TOKEN_ANA)
        padrao = LmRegisterInfo(**KeyBindDefaults.VALUES, **MouseDefaults.VALUES).pack()
        assert corpo[0x00:0x25] == padrao[:0x25]  # conta sem registro: teclas padrão

        chave = cstr(corpo[0x25:0x46])
        async with _connect(ch, CHANNEL_NET_CODE) as c:
            await c.send(CsOp.IN_CHANNEL_SERVER, _chave_payload(chave))
            await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
            await c.expect(CsOp.CHANNEL_INFO_OUT)
            await _saldos_do_login(c)
            await c.send(CsOp.SAVE_OPTION, OPCOES)  # sem resposta
            # O 100 seguinte só é respondido depois de o canal processar o 544.
            await c.send(CsOp.IN_CHANNEL_SERVER, _chave_payload(chave))
            await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
            await c.expect(CsOp.CHANNEL_INFO_OUT)
            await _saldos_do_login(c)

        corpo = await _register_body(msg, TOKEN_ANA)
        assert corpo[0x00:0x25] == OPCOES
        assert corpo[0x00] == 1  # background
        assert corpo[0x05] == 6  # mouse_sensitivity
        assert corpo[0x24] == 37  # screenshot
        assert struct.unpack_from("<i", corpo, 0x48) == (0,)


async def test_save_option_sem_login_ou_curto_e_ignorado(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))

    async with game_servers(settings) as (msg, ch):
        chave = await _chave_de_sessao(msg, TOKEN_ANA)
        async with _connect(ch, CHANNEL_NET_CODE) as c:
            await c.send(CsOp.SAVE_OPTION, OPCOES)  # sem login: ignorado
            await c.send(CsOp.IN_CHANNEL_SERVER, _chave_payload(chave))
            await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
            await c.expect(CsOp.CHANNEL_INFO_OUT)
            await _saldos_do_login(c)
            await c.send(CsOp.SAVE_OPTION, OPCOES[:36])  # 36 bytes: logado e ignorado
            await c.send(CsOp.IN_CHANNEL_SERVER, _chave_payload(chave))  # a conexão continua viva
            await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
            await c.expect(CsOp.CHANNEL_INFO_OUT)
            await _saldos_do_login(c)

        corpo = await _register_body(msg, TOKEN_ANA)
        padrao = LmRegisterInfo(**KeyBindDefaults.VALUES, **MouseDefaults.VALUES).pack()
        assert corpo[0x00:0x25] == padrao[:0x25]


async def test_lobby_lista_todos_com_nick_e_546_responde_so_a_quem_esta_no_lobby(
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
            # A sozinho: a 151 traz o próprio jogador, com o nick em @8 da entrada.
            await a.send(CsOp.IN_CHANNEL_SERVER, _chave_payload(chave_ana))
            await a.expect(CsOp.IN_CHANNEL_SERVER_OUT)
            await a.expect(CsOp.CHANNEL_INFO_OUT)
            await _saldos_do_login(a)
            await a.send(CsOp.IN_CHANNEL)
            lista = await a.expect(CsOp.CHANNEL_PLAYER_INFO_OUT)
            assert lista[0:2] == b"\x01\x00"
            assert struct.unpack_from("<i", lista, 2) == (ana.id,)
            assert cstr(lista[10:26]) == "Ana"
            await a.expect(CsOp.CHANNEL_ROOM_INFO_OUT)
            await a.expect(CsOp.IN_CHANNEL_OUT)

            # B: a 151 traz A e B com o seu nick; A recebe a entrada de B com o nick.
            await b.send(CsOp.IN_CHANNEL_SERVER, _chave_payload(chave_bia))
            await b.expect(CsOp.IN_CHANNEL_SERVER_OUT)
            await b.expect(CsOp.CHANNEL_INFO_OUT)
            await _saldos_do_login(b)
            await b.send(CsOp.IN_CHANNEL)
            lista = await b.expect(CsOp.CHANNEL_PLAYER_INFO_OUT)
            assert lista[0:2] == b"\x02\x00"
            assert cstr(lista[10:26]) == "Ana"
            assert struct.unpack_from("<i", lista, 42) == (bia.id,)
            assert cstr(lista[50:66]) == "Bia"
            await b.expect(CsOp.CHANNEL_ROOM_INFO_OUT)
            await b.expect(CsOp.IN_CHANNEL_OUT)
            entrada = await a.expect(CsOp.IN_CHANNEL_OUT)
            assert cstr(entrada[8:24]) == "Bia"

            # 546: B pede A e um guid que não está no lobby; a 548 traz só A, e a A nada.
            pedido = bytearray(64)
            pedido[4] = 2
            struct.pack_into("<ii", pedido, 8, ana.id, 999_999)
            await b.send(CsOp.REFRESH_PLAYER_LIST, bytes(pedido))
            resposta = await b.expect(CsOp.REFRESH_PLAYER_LIST_OUT)
            assert resposta[0] == 1
            assert struct.unpack_from("<i", resposta, 4) == (ana.id,)
            await a.assert_silencio()


async def test_servidor_envia_heartbeat_periodico() -> None:
    server = await Service(
        net_code=CHANNEL_NET_CODE,
        router={},
        recv_timeout=60,
        heartbeat=CsHeartbeat(),
        heartbeat_every=0.05,
    ).start("127.0.0.1", 0)
    async with server:
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        c = Client(reader, writer, CHANNEL_NET_CODE)
        try:
            assert await c.expect(CsOp.HEARTBEAT) == b""
            assert await c.expect(CsOp.HEARTBEAT) == b""
        finally:
            writer.close()


async def test_tutorial_responde_601_e_passo_sobrevive_ao_reinicio(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))

    async with game_servers(settings) as (msg, ch):
        chave = await _chave_de_sessao(msg, TOKEN_ANA)
        async with _connect(ch, CHANNEL_NET_CODE) as c:
            await c.send(CsOp.IN_CHANNEL_SERVER, _chave_payload(chave))
            await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
            await c.expect(CsOp.CHANNEL_INFO_OUT)
            await _saldos_do_login(c)
            await c.send(CsProgressionOp.TUTORIAL_CLEAR, b"\x00")
            assert await c.expect(CsProgressionOp.TUTORIAL_CLEAR_OUT) == struct.pack("<ii", 1, 0)
            await c.send(CsProgressionOp.TUTORIAL_CLEAR, b"\x02")
            assert await c.expect(CsProgressionOp.TUTORIAL_CLEAR_OUT) == struct.pack("<ii", 5, 0)
            await c.send(CsProgressionOp.TUTORIAL_CLEAR, b"\x03")  # passo 3 não existe
            await c.assert_silencio()

    async with game_servers(settings) as (msg, ch):
        chave = await _chave_de_sessao(msg, TOKEN_ANA)
        async with _connect(ch, CHANNEL_NET_CODE) as c:
            await c.send(CsOp.IN_CHANNEL_SERVER, _chave_payload(chave))
            body = await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
            assert struct.unpack_from("<i", body, 0x28) == (5,)  # iTutorialClear no 101


async def test_grant_aparece_no_login_nos_pushes_e_no_lobby(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana = await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))
    async with open_database(settings) as db:
        await SqlProgressionRepository(db).grant(ana.id, Grant(exp=2800, ld=1000, cash=500))

    async with game_servers(settings) as (msg, ch):
        chave = await _chave_de_sessao(msg, TOKEN_ANA)
        async with _connect(ch, CHANNEL_NET_CODE) as c:
            await c.send(CsOp.IN_CHANNEL_SERVER, _chave_payload(chave))
            body = await c.expect(CsOp.IN_CHANNEL_SERVER_OUT)
            assert struct.unpack_from("<i", body, 0x2C) == (2800,)  # iTotalExp
            assert struct.unpack_from("<i", body, 0x48) == (500,)  # iCash
            assert struct.unpack_from("<i", body, 0x4C) == (1000,)  # iPoint
            await c.expect(CsOp.CHANNEL_INFO_OUT)
            assert await c.expect(CsProgressionOp.CHARGE_CASH_OUT) == struct.pack("<i", 500)
            assert await c.expect(CsProgressionOp.CHARGE_POINT_OUT) == struct.pack("<i", 1000)
            await c.send(CsOp.IN_CHANNEL)
            await c.expect(CsOp.CHANNEL_PLAYER_INFO_OUT)
            await c.expect(CsOp.CHANNEL_ROOM_INFO_OUT)
            body = await c.expect(CsOp.IN_CHANNEL_OUT)
            # O 121 sobrescreve o nó do próprio jogador: a exp não pode voltar a zero.
            assert struct.unpack_from("<i", body, 4) == (2800,)


async def test_desligamento_fecha_conexao_nova_e_o_canal_segue_escutando(tmp_path: Path) -> None:
    """Depois do pedido, conexão nova é fechada logo no accept; o socket segue aberto (D204)."""
    settings = _settings(tmp_path)
    desliga = Shutdown()
    async with game_servers(settings, desliga) as (_msg, channel):
        desliga.begin(300)
        async with _connect(channel, CHANNEL_NET_CODE) as c:
            async with asyncio.timeout(2):
                assert await read_frame(c.reader) is None
        assert channel.is_serving()


async def test_aviso_do_desligamento_chega_a_quem_esta_no_lobby(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with open_accounts(settings) as accounts:
        ana = await accounts.create("ana", "Ana", hash_token(TOKEN_ANA))
    desliga = Shutdown()
    async with game_servers(settings, desliga) as (msg, ch):
        chave = await _chave_de_sessao(msg, TOKEN_ANA)
        async with _connect(ch, CHANNEL_NET_CODE) as c:
            await _entra_no_canal(c, chave, ana.id)
            desliga.begin(0, "Teste")  # prazo já vencido: o aviso sai e o servidor encerra
            await desliga.run()
            corpo = await c.expect(NOTICE_OPCODE)
    texto = "Teste Desligamento em 0 s.".encode("cp1252")
    assert corpo == bytes([len(texto)]) + texto + b"\x00"
