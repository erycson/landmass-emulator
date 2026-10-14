"""Configuração: variáveis `LANDMASS_*` (docs/architecture/05-configuration.md)."""

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChannelConfig(BaseModel):
    name: Annotated[str, Field(max_length=35)] = "Canal 1"
    max_clients: int = 100
    address: Annotated[str | None, Field(max_length=15)] = None
    port: int | None = None
    # `channel_mode` do LM_SERVER_INFO: 0 normal; 6 é CM_CLAN (Core.u). Com 6, o cliente entra na
    # tela de clã; os opcodes de clã do canal ainda não são atendidos (docs/protocol/clan-war.md).
    mode: Annotated[int, Field(ge=0, le=255)] = 0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LANDMASS_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///data/landmass.db"
    bind_host: str = "0.0.0.0"
    public_host: Annotated[str, Field(max_length=15)] = "127.0.0.1"
    message_port: int = 7313
    channel_port: int = 7314
    client_version: int = 1245776779
    client_dir: Path = Path("../cliente/system")
    recv_timeout: Annotated[int, Field(ge=60)] = 300
    channels: Annotated[list[ChannelConfig], Field(min_length=1, max_length=255)] = Field(
        default_factory=lambda: [ChannelConfig()]
    )
    # Sem `match_server_dir`, o 403 (NotifyStartGame) aponta para `game_host:game_port`, fixo.
    # Com a pasta (system\ do servidor-partida), cada sala em partida ganha um processo próprio e
    # uma porta UDP da faixa; o endereço do 403 é `game_host` com a porta da partida.
    game_host: Annotated[str, Field(min_length=1, max_length=15)] = "127.0.0.1"
    game_port: Annotated[int, Field(ge=1, le=65535)] = 7777
    match_server_dir: Path | None = None
    match_port_min: Annotated[int, Field(ge=1024, le=65535)] = 7800
    match_port_max: Annotated[int, Field(ge=1024, le=65535)] = 7899
    match_ready_timeout: Annotated[float, Field(gt=0, le=300)] = 30.0
    # login_num do servidor de partida: o mesmo do cliente de teste (re/game_server_host.md §5).
    match_login_num: Annotated[str | None, Field(max_length=36)] = None
    # Log de economia (compra, destruição, extensão), uma linha JSON por evento (D120).
    audit_log: Path = Path("data/audit/economy.jsonl")

    @model_validator(mode="after")
    def _check_match(self) -> Settings:
        if self.match_port_min > self.match_port_max:
            raise ValueError("LANDMASS_MATCH_PORT_MIN é maior que LANDMASS_MATCH_PORT_MAX")
        if self.match_server_dir is not None and not self.match_login_num:
            raise ValueError("LANDMASS_MATCH_LOGIN_NUM é obrigatório com LANDMASS_MATCH_SERVER_DIR")
        return self
