"""Configuração: variáveis `LANDMASS_*` (docs/architecture/05-configuration.md)."""

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChannelConfig(BaseModel):
    name: Annotated[str, Field(max_length=35)] = "Canal 1"
    max_clients: int = 100
    address: Annotated[str | None, Field(max_length=15)] = None
    port: int | None = None


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
