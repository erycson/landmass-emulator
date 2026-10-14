"""`channel_mode` por canal (D199): vem de `LANDMASS_CHANNELS[].mode`, chega ao `Channel` e fica 0
quando não é configurado. 6 é CM_CLAN (Core.u)."""

import pytest
from pydantic import ValidationError

from landmass_emu.app import channels_from
from landmass_emu.settings import ChannelConfig, Settings


def _settings(*canais: ChannelConfig) -> Settings:
    return Settings(_env_file=None, channels=list(canais))


def test_modo_padrao_e_zero_e_clan_vai_ate_o_canal() -> None:
    normal, clan = channels_from(_settings(ChannelConfig(), ChannelConfig(name="Clã", mode=6)))

    assert normal.mode == 0
    assert clan.mode == 6


def test_modo_fora_de_u8_e_recusado() -> None:
    with pytest.raises(ValidationError):
        ChannelConfig(mode=256)
