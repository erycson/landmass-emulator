"""Repositório de `account_options` em SQLAlchemy async. Implementa `OptionsRepository`."""

import asyncio
from dataclasses import asdict, fields, replace
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.models import OptionsRow
from landmass_emu.protocol.message import LmRegisterInfo

_NAMES = tuple(f.name for f in fields(LmRegisterInfo))


def _to_domain(row: OptionsRow) -> LmRegisterInfo:
    return LmRegisterInfo(**{name: getattr(row, name) for name in _NAMES})


class KeyBindDefaults:
    """Teclas padrão (valores `EInputKey`, que são códigos VK) de conta sem registro e de tecla
    gravada em 0. Fonte: `[Engine.Input]` do `User.ini` do cliente (tools/re/game_server_host.md,
    §12).
    `jump` é a tecla de `CancelStatus`, o pulo do LandMass (`SetAliasToKey(Options.jump,
    "CancelStatus")`): em 0 o personagem não pula. `object` (`TogglePoints`) não tem tecla no
    `User.ini`, e o cliente não liga `screenshot` (linha comentada); os dois ficam em 0.
    shortcut: 0 também é "sem tecla" (IK_None), então uma tecla desligada volta ao padrão no
    próximo 111; upgrade: achar o valor de "sem tecla" no cliente."""

    VALUES: ClassVar[dict[str, int]] = {
        "weapon_0": 48,
        "weapon_1": 49,
        "weapon_2": 50,
        "weapon_3": 51,
        "weapon_4": 52,
        "weapon_5": 53,
        "weapon_6": 54,
        "weapon_7": 55,
        "weapon_8": 56,
        "weapon_9": 57,
        "move_forward": 87,  # W
        "move_backward": 83,  # S
        "move_left": 65,  # A
        "move_right": 68,  # D
        "fire": 1,  # LeftMouse
        "alt_fire": 2,  # RightMouse
        "walk": 17,  # Ctrl
        "down": 70,  # F (Duck)
        "jump": 32,  # Space (CancelStatus)
        "change_mag": 82,  # R
        "chaff": 81,  # Q
        "booster": 16,  # Shift
        "action": 69,  # E (NewUse)
        "speech_menu_1": 67,  # C (ordem inferida dos três SpeechMenuOpen)
        "speech_menu_2": 88,  # X
        "speech_menu_3": 90,  # Z
        "mirror": 73,  # I
        "minimap": 80,  # P
    }

    @classmethod
    def fill(cls, options: LmRegisterInfo) -> LmRegisterInfo:
        """Troca só os campos de tecla em zero. Valor gravado diferente de zero não muda."""
        zeros = {name: v for name, v in cls.VALUES.items() if getattr(options, name) == 0}
        return replace(options, **zeros)


class MouseDefaults:
    """Sensibilidade do mouse de conta sem registro e de sensibilidade gravada em 0. A UI grava o
    valor do slider (`fMouseSence`, XInterface `OnApply`) e o motor recebe
    `clamp(valor * 0.1 + 0.25, 0.25, 10.25)`: 0 cai no piso, o mais lento. 8 vem de
    `MouseSensitivity=1.0` do `User.ini` padrão do UT2004 (`tools/UT2004/Installer/User.ini`,
    linha 345): (1.0 - 0.25) * 10 = 7.5, arredondado para cima. Inferido.
    shortcut: o mínimo e o máximo do slider não foram lidos no cliente; se o slider não chega a 8,
    trocar o padrão. Sem padrão para inverter, voz e volume: 0 é valor válido. A suavização não
    está no bloco de 37 bytes; fica no `User.ini` do cliente (D173)."""

    VALUES: ClassVar[dict[str, int]] = {"mouse_sensitivity": 8}

    @classmethod
    def fill(cls, options: LmRegisterInfo) -> LmRegisterInfo:
        """Troca só a sensibilidade em zero. Valor gravado diferente de zero não muda."""
        zeros = {name: v for name, v in cls.VALUES.items() if getattr(options, name) == 0}
        return replace(options, **zeros)


class SqlOptionsRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions
        # Leitura e depois insert ou update: sem o lock, dois 544 simultâneos da mesma conta
        # poderiam inserir duas linhas e violar `account_options_account_id_unique`.
        self._lock = asyncio.Lock()

    async def get(self, account_id: int) -> LmRegisterInfo:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OptionsRow).where(OptionsRow.account_id == account_id)
            )
        stored = LmRegisterInfo() if row is None else _to_domain(row)
        return MouseDefaults.fill(KeyBindDefaults.fill(stored))

    async def save(self, account_id: int, options: LmRegisterInfo) -> None:
        values = asdict(options)
        now = datetime.now(UTC)
        async with self._lock, self._sessions.begin() as session:
            row = await session.scalar(
                select(OptionsRow).where(OptionsRow.account_id == account_id)
            )
            if row is None:
                session.add(
                    OptionsRow(account_id=account_id, created_at=now, updated_at=now, **values)
                )
                return
            for name, value in values.items():
                setattr(row, name, value)
            row.updated_at = now
