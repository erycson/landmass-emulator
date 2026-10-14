"""Log do processo (D205): texto por padrão, ou uma linha JSON por registro. Sem arquivo
próprio: quem sobe o processo redireciona a saída. O `serve` loga no stdout; os comandos de CLI,
no stderr, para o resultado sair limpo no stdout."""

import json
import logging
from datetime import UTC, datetime
from typing import TextIO


class JsonFormatter(logging.Formatter):
    """Um objeto JSON por linha: `ts` (UTC, ISO), `level`, `logger`, `msg` e, com erro, `exc`."""

    def format(self, record: logging.LogRecord) -> str:
        dados: dict[str, str] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            dados["exc"] = self.formatException(record.exc_info)
        return json.dumps(dados, ensure_ascii=False)


class LogSetup:
    """Liga o log da raiz a `stream`. Devolve o manipulador, para quem quiser desligá-lo depois."""

    def __init__(self, level: str, as_json: bool, stream: TextIO) -> None:
        self._level = level
        self._as_json = as_json
        self._stream = stream

    def apply(self) -> logging.Handler:
        handler = logging.StreamHandler(self._stream)
        if self._as_json:
            handler.setFormatter(JsonFormatter())
        else:
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        raiz = logging.getLogger()
        raiz.setLevel(self._level)
        raiz.addHandler(handler)
        return handler
