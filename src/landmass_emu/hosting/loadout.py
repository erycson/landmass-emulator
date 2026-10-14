"""`LMEmu.ini` da pasta de sistema do servidor de partida: uma seção `[<chave> LMEmuLoadout]` por
partida em andamento, com uma linha `Players=` por jogador (D190).

A leitura e a gravação são em bytes: as seções de outras partidas e o resto do arquivo voltam
idênticos. Só as linhas novas são codificadas (cp1252, com `?` no que não cabe). A troca do arquivo
é atômica (`os.replace`) e serializada pela trava; nada dentro dela é `await`.
"""

import logging
import os
import re
import threading
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

log = logging.getLogger(__name__)

SECTION = "LMEmuLoadout"
HEADER = re.compile(rb"^\s*\[([^\]]*)\]\s*$")
# Linha da seção: texto puro é valor de `Players=` (D190); `(chave, valor)` vai como `chave=valor`
# (`Bots=` e `Owner=`, D220).
Linha = str | tuple[str, str]


class LoadoutFile:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._trava = threading.Lock()

    def write(self, key: str, lines: Sequence[Linha]) -> None:
        """Grava a seção `key`, trocando a antiga se houver. Levanta OSError se não gravar."""
        bloco = [f"[{key} {SECTION}]".encode("ascii"), *(_linha(item) for item in lines)]
        with self._trava:
            self._salva([*_sem_secao(self._linhas(), _nome(key)), *bloco])

    def remove(self, key: str) -> None:
        """Tira a seção `key`. Falha só vai ao log: quem chama já está encerrando a partida."""
        with self._trava:
            try:
                antigas = self._linhas()
                novas = _sem_secao(antigas, _nome(key))
                if len(novas) != len(antigas):
                    self._salva(novas)
            except OSError as e:
                log.warning("LMEmu.ini: seção %s não removida: %s", key, e)

    def _linhas(self) -> list[bytes]:
        try:
            return self._path.read_bytes().splitlines()
        except FileNotFoundError:
            return []

    def _salva(self, linhas: list[bytes]) -> None:
        conteudo = b"".join(linha + b"\r\n" for linha in linhas)
        temporario = self._path.with_name(f"{self._path.name}.{uuid4().hex}.tmp")
        try:
            temporario.write_bytes(conteudo)
            os.replace(temporario, self._path)
        except OSError:
            temporario.unlink(missing_ok=True)
            raise


def _linha(item: Linha) -> bytes:
    chave, valor = ("Players", item) if isinstance(item, str) else item
    return f"{chave}={valor}".encode("cp1252", errors="replace")


def _nome(key: str) -> bytes:
    return f"{key} {SECTION}".encode("ascii")


def _sem_secao(linhas: list[bytes], nome: bytes) -> list[bytes]:
    """Linhas sem a seção `nome`: do cabeçalho dela até o próximo cabeçalho de qualquer seção."""
    saida: list[bytes] = []
    dentro = False
    for linha in linhas:
        casa = HEADER.match(linha)
        if casa is not None:
            dentro = casa.group(1).strip() == nome
        if not dentro:
            saida.append(linha)
    return saida
