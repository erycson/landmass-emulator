"""Canal anunciado pelo Message Server (LM_SERVER_INFO). Vem da configuração."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Channel:
    server_id: int
    name: str
    address: str
    port: int
    max_clients: int
