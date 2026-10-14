"""Configuração: variáveis `LANDMASS_*` e arquivo TOML (docs/architecture/05-configuration.md).

Precedência, da maior para a menor: argumentos, variáveis de ambiente (`.env` conta como ambiente),
`LANDMASS_<CAMPO>_FILE` (segredo lido de arquivo), arquivo TOML e padrão do código.
"""

import os
import tomllib
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

ENV_PREFIX = "LANDMASS_"
CONFIG_ENV = "LANDMASS_CONFIG"


class ChannelConfig(BaseModel):
    name: Annotated[str, Field(max_length=35)] = "Canal 1"
    max_clients: int = 100
    address: Annotated[str | None, Field(max_length=15)] = None
    port: int | None = None
    # `channel_mode` do LM_SERVER_INFO: 0 normal; 6 é CM_CLAN (Core.u). Com 6, o cliente entra na
    # tela de clã; os opcodes de clã do canal ainda não são atendidos (docs/protocol/clan-war.md).
    mode: Annotated[int, Field(ge=0, le=255)] = 0


class _SecretFiles(PydanticBaseSettingsSource):
    """`LANDMASS_<CAMPO>_FILE` lê o valor do arquivo (segredo fora do TOML e do ambiente).
    Com a variável e o arquivo juntos, é erro: não se sabe qual vale."""

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name in self.settings_cls.model_fields:
            var = ENV_PREFIX + name.upper()
            path = os.environ.get(var + "_FILE")
            if path is None:
                continue
            if var in os.environ:
                raise ValueError(f"{var} e {var}_FILE definidas juntas; use só uma")
            out[name] = _read_secret(var + "_FILE", path)
        return out


def _read_secret(var: str, path: str) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"{var}: arquivo não lido: {e}") from e
    # Só o fim de linha sai: um segredo com espaço no meio ou no início fica como está.
    if text.endswith("\r\n"):
        return text[:-2]
    return text[:-1] if text.endswith("\n") else text


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, env_file=".env", extra="ignore")

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
    # Bots (D220): total mínimo de jogadores da partida, humanos e bots (`?MinPlayers=`). Só vale
    # com `match_server_dir`; o motor completa a partida com bots até este número.
    match_bots: Annotated[int, Field(ge=0, le=31)] = 0
    # Log de economia (compra, destruição, extensão), uma linha JSON por evento (D120).
    audit_log: Path = Path("data/audit/economy.jsonl")
    # Desligamento (D202): prazo máximo para sair, avisos antes do prazo e arquivo do comando
    # `shutdown` (D203).
    shutdown_grace_seconds: Annotated[float, Field(ge=0, le=3600)] = 300.0
    shutdown_notice_seconds: list[Annotated[int, Field(ge=1, le=3600)]] = Field(
        default_factory=lambda: [300, 60, 10]
    )
    control_file: Path = Path("data/control/shutdown.json")
    # Log do processo (D205): nível e formato JSON opcional. O serve loga no stdout.
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = False

    @field_validator("shutdown_notice_seconds")
    @classmethod
    def _avisos_unicos(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("LANDMASS_SHUTDOWN_NOTICE_SECONDS não pode repetir valores")
        return sorted(value, reverse=True)

    @model_validator(mode="after")
    def _check_match(self) -> Settings:
        if self.match_port_min > self.match_port_max:
            raise ValueError("LANDMASS_MATCH_PORT_MIN é maior que LANDMASS_MATCH_PORT_MAX")
        if self.match_server_dir is not None and not self.match_login_num:
            raise ValueError("LANDMASS_MATCH_LOGIN_NUM é obrigatório com LANDMASS_MATCH_SERVER_DIR")
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return _sources(settings_cls, init_settings, env_settings, dotenv_settings, None)


def _sources(
    settings_cls: type[BaseSettings],
    init_settings: PydanticBaseSettingsSource,
    env_settings: PydanticBaseSettingsSource,
    dotenv_settings: PydanticBaseSettingsSource,
    toml_file: Path | None,
) -> tuple[PydanticBaseSettingsSource, ...]:
    return (
        init_settings,
        env_settings,
        dotenv_settings,
        _SecretFiles(settings_cls),
        TomlConfigSettingsSource(settings_cls, toml_file=toml_file),
    )


def load_settings(config: Path | None = None) -> Settings:
    """Settings com o arquivo TOML dado (`--config`) ou o de `LANDMASS_CONFIG`. Arquivo informado
    que não existe, e chave que o Settings não conhece, são erro: o TOML ignora em silêncio, e um
    erro de digitação viraria o padrão sem aviso."""
    path = config if config is not None else _config_from_env()
    if path is None:
        return Settings()
    if not path.is_file():
        raise ValueError(f"arquivo de configuração não existe: {path}")
    _check_toml_keys(path)

    class _Configured(Settings):  # classe por chamada: o caminho do TOML entra na fonte
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return _sources(settings_cls, init_settings, env_settings, dotenv_settings, path)

    return _Configured()


def _config_from_env() -> Path | None:
    value = os.environ.get(CONFIG_ENV, "")
    return Path(value) if value else None


def _check_toml_keys(path: Path) -> None:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ValueError(f"{path}: TOML inválido: {e}") from e
    desconhecidas = sorted(set(data) - set(Settings.model_fields))
    if desconhecidas:
        raise ValueError(f"{path}: chaves desconhecidas: {', '.join(desconhecidas)}")
