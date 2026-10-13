"""Modelo SQLAlchemy: `accounts` (marco 1) e `account_options` (F1). Nomes seguem a convenção
Laravel (D11). Colunas de `account_options` na ordem de `LmRegisterInfo`."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AccountRow(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("username", name="accounts_username_unique"),
        UniqueConstraint("nickname", name="accounts_nickname_unique"),
        UniqueConstraint("token_hash", name="accounts_token_hash_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(12))
    nickname: Mapped[str] = mapped_column(String(16))
    token_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OptionsRow(Base):
    __tablename__ = "account_options"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="account_options_account_id_foreign"
        ),
        UniqueConstraint("account_id", name="account_options_account_id_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer)
    background: Mapped[int] = mapped_column(Integer, server_default="0")
    effect: Mapped[int] = mapped_column(Integer, server_default="0")
    voice_info: Mapped[int] = mapped_column(Integer, server_default="0")
    voice_character: Mapped[int] = mapped_column(Integer, server_default="0")
    mouse_acc: Mapped[int] = mapped_column(Integer, server_default="0")
    mouse_sensitivity: Mapped[int] = mapped_column(Integer, server_default="0")
    mouse_invert: Mapped[int] = mapped_column(Integer, server_default="0")
    weapon_1: Mapped[int] = mapped_column(Integer, server_default="0")
    weapon_2: Mapped[int] = mapped_column(Integer, server_default="0")
    weapon_3: Mapped[int] = mapped_column(Integer, server_default="0")
    weapon_4: Mapped[int] = mapped_column(Integer, server_default="0")
    weapon_5: Mapped[int] = mapped_column(Integer, server_default="0")
    weapon_6: Mapped[int] = mapped_column(Integer, server_default="0")
    weapon_7: Mapped[int] = mapped_column(Integer, server_default="0")
    weapon_8: Mapped[int] = mapped_column(Integer, server_default="0")
    weapon_9: Mapped[int] = mapped_column(Integer, server_default="0")
    weapon_0: Mapped[int] = mapped_column(Integer, server_default="0")
    move_forward: Mapped[int] = mapped_column(Integer, server_default="0")
    move_backward: Mapped[int] = mapped_column(Integer, server_default="0")
    move_left: Mapped[int] = mapped_column(Integer, server_default="0")
    move_right: Mapped[int] = mapped_column(Integer, server_default="0")
    fire: Mapped[int] = mapped_column(Integer, server_default="0")
    alt_fire: Mapped[int] = mapped_column(Integer, server_default="0")
    walk: Mapped[int] = mapped_column(Integer, server_default="0")
    down: Mapped[int] = mapped_column(Integer, server_default="0")
    jump: Mapped[int] = mapped_column(Integer, server_default="0")
    change_mag: Mapped[int] = mapped_column(Integer, server_default="0")
    chaff: Mapped[int] = mapped_column(Integer, server_default="0")
    booster: Mapped[int] = mapped_column(Integer, server_default="0")
    action: Mapped[int] = mapped_column(Integer, server_default="0")
    speech_menu_1: Mapped[int] = mapped_column(Integer, server_default="0")
    speech_menu_2: Mapped[int] = mapped_column(Integer, server_default="0")
    speech_menu_3: Mapped[int] = mapped_column(Integer, server_default="0")
    object: Mapped[int] = mapped_column(Integer, server_default="0")
    mirror: Mapped[int] = mapped_column(Integer, server_default="0")
    minimap: Mapped[int] = mapped_column(Integer, server_default="0")
    screenshot: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
