"""Log de economia: uma linha JSON por compra, destruição e extensão, aprovada ou recusada.

Arquivo próprio (`LANDMASS_AUDIT_LOG`), fora do log do servidor e sem tabela (D12, D120). Não grava
token nem chave de sessão.
"""

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from landmass_emu.domain.currency import Currency
from landmass_emu.domain.inventory import ItemUnit, MoratUnit
from landmass_emu.net.session import Session

_LOGGER = "landmass_emu.audit.economy"
# `Session.peer` é `str(peername)`: "('127.0.0.1', 50831)".
_PEER = re.compile(r"\('?([^',]+)'?, (\d+)")


class ItemNames(Protocol):
    def name(self, catalog_id: int) -> str | None: ...


class EconomyAudit:
    """Grava eventos de economia. Sem `open`, o logger não tem destino e nada é escrito."""

    def __init__(self, names: ItemNames | None = None) -> None:
        self._names = names
        self._log = logging.getLogger(_LOGGER)
        self._log.propagate = False

    @classmethod
    def open(cls, path: Path, names: ItemNames | None = None) -> EconomyAudit:
        path.parent.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(_LOGGER)
        if not any(
            getattr(h, "baseFilename", None) == str(path.resolve()) for h in logger.handlers
        ):
            handler = logging.FileHandler(path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return cls(names)

    def record(self, session: Session, event: str, **fields: Any) -> None:
        account = session.account
        ip, port = _split_peer(session.peer)
        self._write(
            event,
            account_id=account.id if account else None,
            username=account.username if account else None,
            nickname=account.nickname if account else None,
            ip=ip,
            port=port,
            fields=fields,
        )

    def record_account(self, account_id: int, nickname: str, event: str, **fields: Any) -> None:
        """Evento de conta sem sessão, como a recompensa de partida: sem usuário, IP nem porta."""
        self._write(
            event,
            account_id=account_id,
            username=None,
            nickname=nickname,
            ip=None,
            port=None,
            fields=fields,
        )

    def _write(
        self,
        event: str,
        *,
        account_id: int | None,
        username: str | None,
        nickname: str | None,
        ip: str | None,
        port: int | None,
        fields: dict[str, Any],
    ) -> None:
        line: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "event": event,
            "account_id": account_id,
            "username": username,
            "nickname": nickname,
            "ip": ip,
            "port": port,
        }
        if "catalog_id" in fields and self._names is not None:
            line["name"] = self._name(fields["catalog_id"])
        line.update(fields)
        self._log.info(json.dumps(line, ensure_ascii=False, default=_json_default))

    def _name(self, catalog_id: int) -> str | None:
        try:
            return self._names.name(catalog_id) if self._names else None
        except ValueError:  # wdb ausente: o evento é gravado sem nome
            return None


def unit_fields(unit: ItemUnit | MoratUnit) -> dict[str, Any]:
    """Identificação da unidade: guid, índice, gate (morat) e prazo."""
    fields: dict[str, Any] = {
        "kind": "morat" if isinstance(unit, MoratUnit) else "item",
        "item_guid": unit.item_guid,
        "inventory_index": unit.inventory_index,
        "expires_at": unit.expires_at,
    }
    if isinstance(unit, MoratUnit):
        fields["gate"] = unit.gate_index
    return fields


def balances(currency: Currency, price: int, *, cash: int, ld: int) -> dict[str, int]:
    """Saldos antes e depois de um débito de `price` em `currency`, a partir dos saldos depois."""
    return {
        "ld_before": ld + price if currency is Currency.LD else ld,
        "ld_after": ld,
        "cash_before": cash + price if currency is Currency.CASH else cash,
        "cash_after": cash,
    }


def _split_peer(peer: str) -> tuple[str, int | None]:
    m = _PEER.match(peer)
    return (m.group(1), int(m.group(2))) if m else (peer, None)


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return str(value)
