"""Canal anunciado pelo Message Server (LM_SERVER_INFO). Vem da configuração."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Channel:
    server_id: int
    name: str
    address: str
    port: int
    max_clients: int
    # channel_mode do LM_SERVER_INFO: 0 normal; 6 é CM_CLAN.
    mode: int = 0
