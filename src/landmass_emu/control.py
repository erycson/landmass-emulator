"""Arquivo de controle do desligamento (D203).

O comando `landmass-emu shutdown` escreve o pedido e o processo em execução o lê e apaga. O pedido
guarda a hora absoluta de saída, porque o comando é outro processo. Sem servidor em execução, o
pedido fica no disco até a próxima subida apagá-lo.
"""

import contextlib
import json
import logging
import os
import time
from pathlib import Path
from typing import NamedTuple

log = logging.getLogger(__name__)


class ShutdownRequest(NamedTuple):
    at: float  # hora de saída, em segundos desde a época (relógio de parede)
    message: str


def write_request(path: Path, after: float, message: str) -> float:
    """Grava o pedido de forma atômica (arquivo temporário e troca). Devolve a hora de saída."""
    at = time.time() + after
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps({"at": at, "message": message}), encoding="utf-8")
    os.replace(temp, path)
    return at


def take_request(path: Path) -> ShutdownRequest | None:
    """Reivindica o pedido renomeando o arquivo antes de lê-lo. Assim, um pedido escrito durante a
    leitura não se perde. Arquivo inválido é apagado e logado."""
    claimed = path.with_name(path.name + ".lido")
    try:
        os.replace(path, claimed)
    except FileNotFoundError:
        return None
    try:
        dados = json.loads(claimed.read_text(encoding="utf-8"))
        return ShutdownRequest(float(dados["at"]), str(dados.get("message", "")))
    except OSError, ValueError, KeyError, TypeError:
        log.warning("pedido de desligamento inválido ignorado: %s", path)
        return None
    finally:
        with contextlib.suppress(FileNotFoundError):
            claimed.unlink()


def discard_request(path: Path) -> None:
    """Apaga um pedido pendente. Chamado na subida: pedido de execução anterior não vale."""
    with contextlib.suppress(FileNotFoundError):
        path.unlink()
