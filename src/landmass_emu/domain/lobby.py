"""Lobby do Channel Server: quem está no canal, em memória. Acessado só pelo loop de eventos."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


class Recipient(Protocol):
    """Destino de corpos já com cabeçalho (`net.session.Session` implementa)."""

    def send(self, body: bytes) -> None: ...


@dataclass(frozen=True, slots=True)
class _Member:
    recipient: Recipient
    nickname: str


class Lobby:
    def __init__(self) -> None:
        self._members: dict[int, _Member] = {}

    def players(self) -> list[tuple[int, str]]:
        """(guid, nickname) de cada membro, na ordem de entrada."""
        return [(guid, m.nickname) for guid, m in self._members.items()]

    def nickname_of(self, guid: int) -> str | None:
        member = self._members.get(guid)
        return None if member is None else member.nickname

    def guid_of(self, recipient: Recipient) -> int | None:
        for guid, member in self._members.items():
            if member.recipient is recipient:
                return guid
        return None

    def join(self, guid: int, recipient: Recipient, nickname: str) -> None:
        # shortcut: a mesma conta em duas conexões substitui a primeira sem avisá-la; revisar
        # quando houver política de sessão única.
        self._members[guid] = _Member(recipient, nickname)

    def leave(self, recipient: Recipient) -> int | None:
        guid = self.guid_of(recipient)
        if guid is not None:
            del self._members[guid]
        return guid

    def is_member(self, guid: int) -> bool:
        return guid in self._members

    def broadcast(self, body: bytes, *, exclude: Recipient | None = None) -> None:
        for member in self._members.values():
            if member.recipient is not exclude:
                member.recipient.send(body)

    def send_to(self, guids: Iterable[int], body: bytes) -> None:
        """Envia a quem está no lobby entre `guids`; quem saiu do lobby é ignorado."""
        for guid in guids:
            member = self._members.get(guid)
            if member is not None:
                member.recipient.send(body)
