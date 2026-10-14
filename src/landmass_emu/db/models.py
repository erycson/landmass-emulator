"""Modelo SQLAlchemy: `accounts` (marco 1, progressão em F2 e F3, regular em F5), `account_options`
(F1), `account_morats` (F5), `account_items` (F4), `friends` e `blocks` (F12). Nomes seguem a
convenção Laravel (D11). Colunas de `account_options` na ordem de `LmRegisterInfo`."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint
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
    tutorial_clear: Mapped[int] = mapped_column(Integer, server_default="0")
    total_exp: Mapped[int] = mapped_column(Integer, server_default="0")
    ld: Mapped[int] = mapped_column(Integer, server_default="0")
    cash: Mapped[int] = mapped_column(Integer, server_default="0")
    regular_nest_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    regular_morat_class: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AccountMoratRow(Base):
    __tablename__ = "account_morats"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="account_morats_account_id_foreign"
        ),
        UniqueConstraint(
            "account_id", "inventory_index", name="account_morats_account_id_inventory_index_unique"
        ),
        UniqueConstraint("item_guid", name="account_morats_item_guid_unique"),
        UniqueConstraint(
            "account_id", "gate_index", name="account_morats_account_id_gate_index_unique"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer)
    inventory_index: Mapped[int] = mapped_column(Integer)
    catalog_id: Mapped[int] = mapped_column(Integer)
    item_guid: Mapped[str] = mapped_column(String(36))
    gate_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    apply_flag: Mapped[int] = mapped_column(Integer, server_default="0")
    apply_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AccountItemRow(Base):
    __tablename__ = "account_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="account_items_account_id_foreign"
        ),
        ForeignKeyConstraint(
            ["account_morat_id"],
            ["account_morats.id"],
            name="account_items_account_morat_id_foreign",
            ondelete="SET NULL",
        ),
        UniqueConstraint(
            "account_id", "inventory_index", name="account_items_account_id_inventory_index_unique"
        ),
        UniqueConstraint("item_guid", name="account_items_item_guid_unique"),
        UniqueConstraint(
            "account_morat_id", "slot_name", name="account_items_account_morat_id_slot_name_unique"
        ),
        UniqueConstraint(
            "account_id", "system_slot", name="account_items_account_id_system_slot_unique"
        ),
        Index("account_items_account_morat_id_index", "account_morat_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer)
    inventory_index: Mapped[int] = mapped_column(Integer)
    catalog_id: Mapped[int] = mapped_column(Integer)
    item_guid: Mapped[str] = mapped_column(String(36))
    account_morat_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slot_name: Mapped[str | None] = mapped_column(String(20), nullable=True)
    system_slot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    apply_flag: Mapped[int] = mapped_column(Integer, server_default="0")
    apply_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class FriendRow(Base):
    """Amizade dirigida: adicionar B em A não muda B (07-progression §4.7)."""

    __tablename__ = "friends"
    __table_args__ = (
        ForeignKeyConstraint(["account_id"], ["accounts.id"], name="friends_account_id_foreign"),
        ForeignKeyConstraint(
            ["friend_account_id"], ["accounts.id"], name="friends_friend_account_id_foreign"
        ),
        UniqueConstraint(
            "account_id", "friend_account_id", name="friends_account_id_friend_account_id_unique"
        ),
        Index("friends_friend_account_id_index", "friend_account_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer)
    friend_account_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BlockRow(Base):
    """Bloqueio dirigido: mesma estrutura de `friends` (07-progression §4.7)."""

    __tablename__ = "blocks"
    __table_args__ = (
        ForeignKeyConstraint(["account_id"], ["accounts.id"], name="blocks_account_id_foreign"),
        ForeignKeyConstraint(
            ["blocked_account_id"], ["accounts.id"], name="blocks_blocked_account_id_foreign"
        ),
        UniqueConstraint(
            "account_id", "blocked_account_id", name="blocks_account_id_blocked_account_id_unique"
        ),
        Index("blocks_blocked_account_id_index", "blocked_account_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer)
    blocked_account_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
