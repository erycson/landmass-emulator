import asyncio
import ftplib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from landmass_emu.update.ftp import FtpServer


async def _sobe(root: Path, user: str = "", password: str = "") -> tuple[asyncio.Server, int]:
    server = await FtpServer(root, user, password).start("127.0.0.1", 0)
    return server, int(server.sockets[0].getsockname()[1])


async def _roda(server: asyncio.Server, fn: Callable[[], Any]) -> Any:
    try:
        return await asyncio.to_thread(fn)
    finally:
        server.close()
        await server.wait_closed()


def _cliente(port: int, user: str = "anonymous", password: str = "x") -> ftplib.FTP:
    ftp = ftplib.FTP()
    ftp.connect("127.0.0.1", port, timeout=10)
    try:
        ftp.login(user, password)
    except ftplib.error_perm:
        ftp.close()  # sem isto, a sessão fica aberta e `wait_closed` do servidor trava
        raise
    return ftp


async def test_pasta_vazia_lista_sem_arquivos(tmp_path: Path) -> None:
    server, port = await _sobe(tmp_path)

    def cena() -> tuple[list[str], list[str], str]:
        with _cliente(port) as ftp:
            linhas: list[str] = []
            ftp.retrlines("LIST", linhas.append)
            return ftp.nlst(), linhas, ftp.pwd()

    nomes, linhas, pwd = await _roda(server, cena)
    assert nomes == []
    assert linhas == []
    assert pwd == "/"


async def test_lista_baixa_e_mede_arquivo(tmp_path: Path) -> None:
    (tmp_path / "version.ini").write_bytes(b"1245776779\n")
    (tmp_path / "pacote").mkdir()
    (tmp_path / "pacote" / "a.bin").write_bytes(b"\x00\x01\x02" * 40000)  # > um bloco
    server, port = await _sobe(tmp_path)

    def cena() -> tuple[list[str], list[str], bytes, int, bytes]:
        with _cliente(port) as ftp:
            linhas: list[str] = []
            ftp.retrlines("LIST", linhas.append)
            dados = bytearray()
            ftp.retrbinary("RETR version.ini", dados.extend)
            grande = bytearray()
            ftp.cwd("pacote")
            ftp.retrbinary("RETR a.bin", grande.extend)
            return ftp.nlst("/"), linhas, bytes(dados), ftp.size("/version.ini") or 0, bytes(grande)

    nomes, linhas, dados, tamanho, grande = await _roda(server, cena)
    assert "version.ini" in nomes and "pacote" in nomes
    assert any(linha.endswith(" version.ini") and linha.startswith("-rw") for linha in linhas)
    assert any(linha.endswith(" pacote") and linha.startswith("drw") for linha in linhas)
    assert dados == b"1245776779\n"
    assert tamanho == len(b"1245776779\n")
    assert grande == b"\x00\x01\x02" * 40000


async def test_nao_sai_da_pasta_de_atualizacao(tmp_path: Path) -> None:
    raiz = tmp_path / "update"
    raiz.mkdir()
    (tmp_path / "segredo.txt").write_bytes(b"fora")
    server, port = await _sobe(raiz)

    def cena() -> tuple[str, Exception | None]:
        with _cliente(port) as ftp:
            ftp.cwd("..")  # fica na raiz
            pwd = ftp.pwd()
            try:
                ftp.retrbinary("RETR ../segredo.txt", lambda _: None)
            except ftplib.error_perm as e:
                return pwd, e
            return pwd, None

    pwd, erro = await _roda(server, cena)
    assert pwd == "/"
    assert isinstance(erro, ftplib.error_perm) and str(erro).startswith("550")


async def test_login_com_usuario_e_senha_configurados(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_bytes(b"ok")
    server, port = await _sobe(tmp_path, "launcher", "segredo")

    def cena() -> bool:
        with pytest.raises(ftplib.error_perm):
            _cliente(port, "launcher", "errada")
        with pytest.raises(ftplib.error_perm):
            _cliente(port, "outro", "segredo")
        with _cliente(port, "launcher", "segredo") as ftp:
            return "x.txt" in ftp.nlst()

    assert await _roda(server, cena)


async def _cru(port: int, *linhas: bytes) -> list[str]:
    """Cliente cru: manda as linhas e devolve as respostas (uma por linha, sem CRLF)."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    respostas = [(await reader.readline()).decode().strip()]
    for linha in linhas:
        writer.write(linha + b"\r\n")
        await writer.drain()
        respostas.append((await asyncio.wait_for(reader.readline(), 10)).decode().strip())
    writer.close()
    await writer.wait_closed()
    return respostas


async def test_comando_antes_do_login_e_desconhecido(tmp_path: Path) -> None:
    server, port = await _sobe(tmp_path)
    try:
        respostas = await _cru(
            port, b"PWD", b"XYZZY", b"USER anonymous", b"PASS x", b"PWD", b"QUIT"
        )
    finally:
        server.close()
        await server.wait_closed()
    assert respostas[0].startswith("220")
    assert respostas[1].startswith("530")
    assert respostas[2].startswith("502")
    assert respostas[3].startswith("331")
    assert respostas[4].startswith("230")
    assert respostas[5].startswith('257 "/"')
    assert respostas[6].startswith("221")


async def test_list_sem_pasv_recusa(tmp_path: Path) -> None:
    server, port = await _sobe(tmp_path)
    try:
        respostas = await _cru(
            port, b"USER anonymous", b"PASS x", b"LIST", b"SIZE nao_existe", b"QUIT"
        )
    finally:
        server.close()
        await server.wait_closed()
    assert respostas[3].startswith("425")
    assert respostas[4].startswith("550")
