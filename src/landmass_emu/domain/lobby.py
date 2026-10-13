"""Lobby do Channel Server: quem está no canal, em memória. Acessado só pelo loop de eventos."""

from typing import Protocol


class Recipient(Protocol):
    """Destino de corpos já com cabeçalho (`net.session.Session` implementa)."""

    def send(self, body: bytes) -> None: ...


class Lobby:
    def __init__(self) -> None:
        self._members: dict[int, Recipient] = {}

    def guids(self) -> list[int]:
        return list(self._members)

    def guid_of(self, recipient: Recipient) -> int | None:
        for guid, member in self._members.items():
            if member is recipient:
                return guid
        return None

    def join(self, guid: int, recipient: Recipient) -> None:
        # shortcut: a mesma conta em duas conexões substitui a primeira sem avisá-la; revisar
        # quando houver política de sessão única.
        self._members[guid] = recipient

    def leave(self, recipient: Recipient) -> int | None:
        guid = self.guid_of(recipient)
        if guid is not None:
            del self._members[guid]
        return guid

    def broadcast(self, body: bytes, *, exclude: Recipient | None = None) -> None:
        for member in self._members.values():
            if member is not exclude:
                member.send(body)
