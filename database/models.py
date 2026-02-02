from typing import Optional

from sqlalchemy import DateTime, Date, String, Text, Integer, Boolean, func, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    created: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

class User(Base):
    __tablename__ = 'user'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    phone: Mapped[int] = mapped_column(Integer, nullable=False)
    email: Mapped[str] = mapped_column(String(128))
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    user_name: Mapped[Optional[str]] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16), default='user', nullable=False)
    generations_made: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generations_left: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    bonus_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bonus_left: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    selected_store_id: Mapped[Optional[int]] = mapped_column(ForeignKey("store.id", ondelete="SET NULL"), nullable=True)

    stores: Mapped[list["Store"]] = relationship(
        "Store",
        foreign_keys="[Store.tg_id]",
        back_populates="user",
        primaryjoin="User.tg_id == Store.tg_id")
    selected_store: Mapped[Optional["Store"]] = relationship(
        "Store",
        foreign_keys=[selected_store_id],
    )
    reports: Mapped[list["Report"]] = relationship("Report")
    payments: Mapped[list["Payment"]] = relationship("Payment")
    referrals: Mapped[list["Ref"]] = relationship("Ref", foreign_keys="[Ref.referrer_id]")


class Store(Base):
    __tablename__ = 'store'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(ForeignKey("user.tg_id"), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    token: Mapped[str] = mapped_column(String(512), nullable=False)

    reports: Mapped[list["Report"]] = relationship("Report")
    user: Mapped["User"] = relationship("User", back_populates="stores", foreign_keys=[tg_id])


class Report(Base):
    __tablename__ = 'report'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(ForeignKey("user.tg_id"), nullable=False)
    date_of_week: Mapped[Date] = mapped_column(Date, nullable=False)
    report_path: Mapped[str] = mapped_column(String, nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("store.id"), nullable=False)


class Ref(Base):
    __tablename__ = 'ref'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    referral_id: Mapped[int] = mapped_column(nullable=False, unique=True)
    referrer_id: Mapped[int] = mapped_column(ForeignKey("user.tg_id"), nullable=False)

    __table_args__ = (
        Index('idx_referral_unique', 'referral_id', unique=True),  # явное указание индекса
    )


class Payment(Base):
    __tablename__ = 'payment'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(ForeignKey("user.tg_id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    generations_num: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source: Mapped[str] = mapped_column((String(16)), nullable=False)
    yoo_id: Mapped[str] = mapped_column(String(64))
