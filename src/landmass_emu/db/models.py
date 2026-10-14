"""Modelo SQLAlchemy: `accounts` (marco 1, progressão em F2 e F3, regular em F5), `account_options`
(F1), `account_morats` (F5), `account_items` (F4), `account_quick_slots` (D73), `friends` e
`blocks` (F12), `matches` e `match_players` (histórico de partidas), `clans` e `clan_members` (F13),
`shop_items` (venda da loja, D191). Nomes seguem a convenção Laravel (D11). Colunas de
`account_options` na ordem de `LmRegisterInfo`."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
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
    # Bloqueio temporário pela CLI (D106): nulo = sem bloqueio.
    banned_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Marcos de zerado (D131, D132): a ficha conta só partidas depois. Nulo = nunca zerado.
    record_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    combat_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gate_count: Mapped[int] = mapped_column(Integer, server_default="4")
    # Nível de acesso GM (D193): 0 jogador; 9 ou mais tem comandos de GM. Gravado pela CLI.
    access_level: Mapped[int] = mapped_column(Integer, server_default="0")


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


class GiftRow(Base):
    """Depósito (F10): presente pendente de um destinatário até o resgate (612). `claimed_at` nulo
    = pendente. `slot` é a chave u16 do 610/612, única entre os pendentes da conta."""

    __tablename__ = "gifts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["sender_account_id"], ["accounts.id"], name="gifts_sender_account_id_foreign"
        ),
        ForeignKeyConstraint(
            ["receiver_account_id"], ["accounts.id"], name="gifts_receiver_account_id_foreign"
        ),
        Index("gifts_receiver_account_id_index", "receiver_account_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    receiver_account_id: Mapped[int] = mapped_column(Integer)
    slot: Mapped[int] = mapped_column(Integer)
    catalog_id: Mapped[int] = mapped_column(Integer)
    duration_days: Mapped[int] = mapped_column(Integer)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AccountQuickSlotRow(Base):
    __tablename__ = "account_quick_slots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="account_quick_slots_account_id_foreign"
        ),
        UniqueConstraint(
            "account_id", "slot_index", name="account_quick_slots_account_id_slot_index_unique"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer)
    slot_index: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[int] = mapped_column(Integer, server_default="0")
    memo: Mapped[str] = mapped_column(String(8), server_default="")
    gate_index: Mapped[int] = mapped_column(Integer)
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


class MatchRow(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("uuid", name="matches_uuid_unique"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(Integer)
    map_record_id: Mapped[int] = mapped_column(Integer)
    map_file: Mapped[str] = mapped_column(String(64))
    game_mode: Mapped[int] = mapped_column(Integer)
    game_class: Mapped[str] = mapped_column(String(64))
    team_count: Mapped[int] = mapped_column(Integer)
    max_players: Mapped[int] = mapped_column(Integer)
    time_limit: Mapped[int] = mapped_column(Integer)
    goal_score: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_reason: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Colunas depois de updated_at: a migração 5c1e8a3f7b92 as acrescenta no fim da tabela.
    uuid: Mapped[str | None] = mapped_column(String(36))


class MatchPlayerRow(Base):
    __tablename__ = "match_players"
    __table_args__ = (
        ForeignKeyConstraint(["match_id"], ["matches.id"], name="match_players_match_id_foreign"),
        UniqueConstraint("match_id", "account_id", name="match_players_match_id_account_id_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    nickname: Mapped[str] = mapped_column(String(16))
    slot: Mapped[int] = mapped_column(Integer)
    team: Mapped[int | None] = mapped_column(Integer)
    is_master: Mapped[bool] = mapped_column(Boolean)
    kills: Mapped[int | None] = mapped_column(Integer)
    deaths: Mapped[int | None] = mapped_column(Integer)
    assists: Mapped[int | None] = mapped_column(Integer)
    ranking: Mapped[int | None] = mapped_column(Integer)
    played_percent: Mapped[float | None] = mapped_column(Float)
    won: Mapped[bool | None] = mapped_column(Boolean)
    headshots: Mapped[int | None] = mapped_column(Integer)
    bullets: Mapped[int | None] = mapped_column(Integer)
    hits: Mapped[int | None] = mapped_column(Integer)
    damage: Mapped[int | None] = mapped_column(Integer)
    exp: Mapped[int | None] = mapped_column(Integer)
    money: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    played_seconds: Mapped[int | None] = mapped_column(Integer)


class ClanRow(Base):
    """Clã (F13, 07-progression §4.8). Sem tabela de log: `tbl_clanlog` é log (D12)."""

    __tablename__ = "clans"
    __table_args__ = (
        ForeignKeyConstraint(
            ["master_account_id"], ["accounts.id"], name="clans_master_account_id_foreign"
        ),
        UniqueConstraint("name", name="clans_name_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(16))
    master_account_id: Mapped[int] = mapped_column(Integer)
    mark: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ClanMemberRow(Base):
    """Membro de clã. Uma conta, no máximo um clã (D60)."""

    __tablename__ = "clan_members"
    __table_args__ = (
        ForeignKeyConstraint(["clan_id"], ["clans.id"], name="clan_members_clan_id_foreign"),
        ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="clan_members_account_id_foreign"
        ),
        UniqueConstraint("account_id", name="clan_members_account_id_unique"),
        Index("clan_members_clan_id_index", "clan_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clan_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    grade: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ShopItemRow(Base):
    """Venda da loja (D191): um id do catálogo com preço por nível (0 a 3) em cada moeda. Preço
    zero = não vendido nesta moeda. `enabled` falso recusa a compra. `ld` no ORM é `point` no banco
    (o nome do wdb e do `landmass-emu shop price --point`)."""

    __tablename__ = "shop_items"

    catalog_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean)
    point_0: Mapped[int] = mapped_column(Integer, server_default="0")
    point_1: Mapped[int] = mapped_column(Integer, server_default="0")
    point_2: Mapped[int] = mapped_column(Integer, server_default="0")
    point_3: Mapped[int] = mapped_column(Integer, server_default="0")
    cash_0: Mapped[int] = mapped_column(Integer, server_default="0")
    cash_1: Mapped[int] = mapped_column(Integer, server_default="0")
    cash_2: Mapped[int] = mapped_column(Integer, server_default="0")
    cash_3: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
