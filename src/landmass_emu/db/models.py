"""Modelo SQLAlchemy. Só `tbl_account` (marco 1); nomes de tabela e coluna originais (D6)."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AccountRow(Base):
    __tablename__ = "tbl_account"
    __table_args__ = (
        UniqueConstraint("userid", name="uq_tbl_account_userid"),
        UniqueConstraint("nick", name="uq_tbl_account_nick"),
        UniqueConstraint("token_hash", name="uq_tbl_account_token_hash"),
    )

    account_code: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userid: Mapped[str] = mapped_column(String(12))
    nick: Mapped[str] = mapped_column(String(16))
    token_hash: Mapped[str] = mapped_column(String(64))
    create_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
