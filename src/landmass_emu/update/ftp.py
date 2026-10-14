"""Servidor FTP mínimo de atualização (D241). Só leitura de uma pasta, modo passivo, asyncio.

O Launcher usa WinINet (`CFtpConnection`, `FtpFindFirstFileW`). Comandos atendidos: USER, PASS,
SYST, FEAT, PWD, CWD, CDUP, TYPE, MODE, STRU, PASV, EPSV, LIST, NLST, SIZE, RETR, NOOP, QUIT. Modo
ativo (PORT) e escrita (STOR, DELE, MKD...) não são atendidos: respondem 502 ou 550.
Desligado por padrão (`LANDMASS_UPDATE_PORT`).
"""

import asyncio
import contextlib
import hmac
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path, PurePosixPath

IDLE_SECONDS = 300.0
DATA_TIMEOUT = 30.0
MAX_LINE = 4096
CHUNK = 65536

log = logging.getLogger(__name__)

_Stream = tuple[asyncio.StreamReader, asyncio.StreamWriter]


class FtpServer:
    def __init__(self, root: Path, user: str = "", password: str = "") -> None:
        self._root = root.resolve()
        self._user = user
        self._password = password

    @property
    def root(self) -> Path:
        return self._root

    def check_login(self, user: str, password: str) -> bool:
        """Sem usuário configurado, aceita qualquer login (a pasta é só de leitura). Com usuário,
        confere usuário e, se houver, senha. Comparação em tempo constante."""
        if not self._user:
            return True
        if not hmac.compare_digest(user.encode(), self._user.encode()):
            return False
        if not self._password:
            return True
        return hmac.compare_digest(password.encode(), self._password.encode())

    async def start(self, host: str, port: int) -> asyncio.Server:
        return await asyncio.start_server(self._serve, host, port)

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        log.info("FTP: conexão de %s", writer.get_extra_info("peername"))
        session = FtpSession(self, reader, writer)
        try:
            await session.run()
        except ConnectionError, asyncio.IncompleteReadError, ValueError:
            pass
        finally:
            session.close_passive()
            writer.close()


class FtpSession:
    def __init__(
        self, server: FtpServer, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self._server = server
        self._reader = reader
        self._writer = writer
        self._cwd = PurePosixPath("/")
        self._user = ""
        self._logged_in = False
        self._listener: asyncio.Server | None = None
        self._incoming: asyncio.Future[_Stream] | None = None
        self._commands: dict[str, Callable[[str], Awaitable[bool]]] = {
            "USER": self._user_cmd,
            "PASS": self._pass_cmd,
            "QUIT": self._quit_cmd,
            "NOOP": self._noop_cmd,
            "SYST": self._syst_cmd,
            "FEAT": self._feat_cmd,
            "TYPE": self._type_cmd,
            "MODE": self._ok_cmd,
            "STRU": self._ok_cmd,
            "PWD": self._pwd_cmd,
            "XPWD": self._pwd_cmd,
            "CWD": self._cwd_cmd,
            "CDUP": self._cdup_cmd,
            "PASV": self._pasv_cmd,
            "EPSV": self._epsv_cmd,
            "LIST": self._list_cmd,
            "NLST": self._nlst_cmd,
            "SIZE": self._size_cmd,
            "RETR": self._retr_cmd,
        }

    async def run(self) -> None:
        await self._reply(220, "LandMass atualização")
        while True:
            try:
                raw = await asyncio.wait_for(self._reader.readline(), IDLE_SECONDS)
            except TimeoutError:
                await self._reply(421, "Tempo esgotado")
                return
            if not raw:
                return
            if len(raw) > MAX_LINE:
                await self._reply(500, "Linha longa demais")
                return
            verb, _, arg = raw.decode("utf-8", errors="replace").strip().partition(" ")
            if not await self._dispatch(verb.upper(), arg.strip()):
                return

    def close_passive(self) -> None:
        """Fecha o ouvinte passivo. Não espera as conexões: esperar aqui trava a transferência."""
        self._incoming = None
        if self._listener is not None:
            self._listener.close()
            self._listener = None

    async def _dispatch(self, verb: str, arg: str) -> bool:
        log.info("FTP: %s %s", verb, "***" if verb == "PASS" else arg)
        handler = self._commands.get(verb)
        if handler is None:
            await self._reply(502, "Comando não implementado")
            return True
        if not self._logged_in and verb not in ("USER", "PASS", "QUIT", "NOOP", "FEAT", "SYST"):
            await self._reply(530, "Faça login")
            return True
        return await handler(arg)

    async def _reply(self, code: int, text: str) -> None:
        log.info("FTP: -> %d %s", code, text)
        self._writer.write(f"{code} {text}\r\n".encode("utf-8", errors="replace"))
        await self._writer.drain()

    async def _user_cmd(self, arg: str) -> bool:
        self._user = arg
        await self._reply(331, "Informe a senha")
        return True

    async def _pass_cmd(self, arg: str) -> bool:
        if not self._user:
            await self._reply(503, "Informe o usuário antes")
            return True
        self._logged_in = self._server.check_login(self._user, arg)
        if self._logged_in:
            await self._reply(230, "Login feito")
        else:
            self._user = ""
            await self._reply(530, "Login ou senha inválidos")
        return True

    async def _quit_cmd(self, arg: str) -> bool:
        await self._reply(221, "Até logo")
        return False

    async def _noop_cmd(self, arg: str) -> bool:
        await self._reply(200, "OK")
        return True

    async def _syst_cmd(self, arg: str) -> bool:
        await self._reply(215, "UNIX Type: L8")
        return True

    async def _feat_cmd(self, arg: str) -> bool:
        self._writer.write(b"211-Recursos\r\n PASV\r\n EPSV\r\n SIZE\r\n211 Fim\r\n")
        await self._writer.drain()
        return True

    async def _ok_cmd(self, arg: str) -> bool:
        await self._reply(200, "OK")
        return True

    async def _type_cmd(self, arg: str) -> bool:
        if arg.upper() in ("A", "I"):
            await self._reply(200, f"Tipo {arg.upper()}")
        else:
            await self._reply(504, "Tipo não suportado")
        return True

    async def _pwd_cmd(self, arg: str) -> bool:
        await self._reply(257, f'"{self._cwd}" é o diretório atual')
        return True

    async def _cwd_cmd(self, arg: str) -> bool:
        target = self._resolve(arg)
        if target is None or not target[1].is_dir():
            await self._reply(550, "Diretório não existe")
        else:
            self._cwd = target[0]
            await self._reply(250, "Diretório alterado")
        return True

    async def _cdup_cmd(self, arg: str) -> bool:
        return await self._cwd_cmd("..")

    async def _pasv_cmd(self, arg: str) -> bool:
        host = str(self._writer.get_extra_info("sockname")[0])
        if ":" in host:
            await self._reply(425, "PASV exige IPv4; use EPSV")
            return True
        port = await self._open_passive(host)
        numbers = ",".join([*host.split("."), str(port >> 8), str(port & 0xFF)])
        await self._reply(227, f"Modo passivo ({numbers})")
        return True

    async def _epsv_cmd(self, arg: str) -> bool:
        host = str(self._writer.get_extra_info("sockname")[0])
        port = await self._open_passive(host)
        await self._reply(229, f"Modo passivo estendido (|||{port}|)")
        return True

    async def _list_cmd(self, arg: str) -> bool:
        return await self._send_listing(arg, unix=True)

    async def _nlst_cmd(self, arg: str) -> bool:
        return await self._send_listing(arg, unix=False)

    async def _size_cmd(self, arg: str) -> bool:
        target = self._resolve(arg)
        if target is None or not target[1].is_file():
            await self._reply(550, "Arquivo não existe")
        else:
            await self._reply(213, str(target[1].stat().st_size))
        return True

    async def _retr_cmd(self, arg: str) -> bool:
        target = self._resolve(arg)
        if target is None or not target[1].is_file():
            await self._reply(550, "Arquivo não existe")
            return True
        conn = await self._take_data_connection()
        if conn is None:
            return True
        _, data_writer = conn
        await self._reply(150, f"Enviando {target[1].name}")
        try:
            with target[1].open("rb") as f:
                while chunk := f.read(CHUNK):
                    data_writer.write(chunk)
                    await data_writer.drain()
        except ConnectionError:
            await self._reply(426, "Conexão de dados perdida")
        else:
            await self._reply(226, "Transferência concluída")
        finally:
            await _close_data(data_writer)
        return True

    async def _send_listing(self, arg: str, *, unix: bool) -> bool:
        # Opções como `LIST -la` são ignoradas; o argumento, se houver, é o diretório.
        target = self._resolve("" if not arg or arg.startswith("-") else arg)
        if target is None or not target[1].is_dir():
            await self._reply(550, "Diretório não existe")
            return True
        conn = await self._take_data_connection()
        if conn is None:
            return True
        _, data_writer = conn
        await self._reply(150, "Lista de arquivos")
        try:
            entries = sorted(target[1].iterdir(), key=lambda p: p.name.lower())
            lines = [_unix_line(e) if unix else e.name for e in entries]
            data_writer.write("".join(f"{line}\r\n" for line in lines).encode("utf-8", "replace"))
            await data_writer.drain()
        except ConnectionError:
            await self._reply(426, "Conexão de dados perdida")
        else:
            await self._reply(226, "Lista enviada")
        finally:
            await _close_data(data_writer)
        return True

    def _resolve(self, arg: str) -> tuple[PurePosixPath, Path] | None:
        """Caminho virtual e local dentro da pasta de atualização, ou None se escapa dela."""
        virtual = PurePosixPath(arg) if arg.startswith("/") else self._cwd / arg
        parts: list[str] = []
        for part in virtual.parts:
            if part in ("/", ".", ""):
                continue
            if part == "..":
                if parts:
                    parts.pop()
                continue
            if any(c in part for c in "\\:\0"):
                return None
            parts.append(part)
        local = (self._server.root / Path(*parts)).resolve()
        if not local.is_relative_to(self._server.root):
            return None
        return PurePosixPath("/", *parts), local

    async def _open_passive(self, host: str) -> int:
        """Abre o ouvinte de dados numa porta livre e devolve a porta. A conexão aceita vai para
        `_incoming`; o ouvinte é fechado logo depois que ela chega."""
        self.close_passive()
        loop = asyncio.get_running_loop()
        self._incoming = loop.create_future()

        async def accept(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            if self._incoming is not None and not self._incoming.done():
                self._incoming.set_result((reader, writer))
            else:
                writer.close()

        self._listener = await asyncio.start_server(accept, host, 0)
        return int(self._listener.sockets[0].getsockname()[1])

    async def _take_data_connection(self) -> _Stream | None:
        if self._incoming is None:
            await self._reply(425, "Use PASV ou EPSV antes")
            return None
        # `_incoming` só some em `close_passive`: se a conexão chega antes da espera, o `accept`
        # ainda precisa dele; zerá-lo aqui fecharia a conexão de dados.
        try:
            return await asyncio.wait_for(self._incoming, DATA_TIMEOUT)
        except TimeoutError:
            await self._reply(425, "Conexão de dados não abriu")
            return None
        finally:
            self.close_passive()


async def _close_data(writer: asyncio.StreamWriter) -> None:
    writer.close()
    with contextlib.suppress(ConnectionError):
        await writer.wait_closed()


def _unix_line(entry: Path) -> str:
    st = entry.stat()
    kind = "d" if entry.is_dir() else "-"
    mode = "rwxr-xr-x" if entry.is_dir() else "rw-r--r--"
    when = datetime.fromtimestamp(st.st_mtime).strftime("%b %d %H:%M")
    return f"{kind}{mode} 1 ftp ftp {st.st_size:>12} {when} {entry.name}"
