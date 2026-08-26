from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    points: Mapped[int] = mapped_column(BigInteger, default=0)
    fcoins: Mapped[int] = mapped_column(Integer, default=0)
    next_card_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    luck_lvl: Mapped[int] = mapped_column(Integer, default=0)
    speed_lvl: Mapped[int] = mapped_column(Integer, default=0)
    trader_lvl: Mapped[int] = mapped_column(Integer, default=0)
    farmer_lvl: Mapped[int] = mapped_column(Integer, default=0)
    workshop_lvl: Mapped[int] = mapped_column(Integer, default=0)
    workshop_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    daily_day: Mapped[int] = mapped_column(Integer, default=0)
    daily_last: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cards_opened: Mapped[int] = mapped_column(Integer, default=0)
    upgrades_done: Mapped[int] = mapped_column(Integer, default=0)
    sales_done: Mapped[int] = mapped_column(Integer, default=0)
    casino_wins: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserCard(Base):
    __tablename__ = "user_cards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    rarity: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(64))
    weight: Mapped[int] = mapped_column(Integer)
    defects: Mapped[list] = mapped_column(JSON, default=list)
    base_price: Mapped[int] = mapped_column(BigInteger, default=0)
    listed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Accessory(Base):
    __tablename__ = "accessories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    item_key: Mapped[str] = mapped_column(String(32))
    __table_args__ = (UniqueConstraint("user_id", "item_key", name="uq_user_item"),)


class MarketListing(Base):
    __tablename__ = "market_listings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_cards.id"), unique=True)
    seller_id: Mapped[int] = mapped_column(BigInteger, index=True)
    price: Mapped[int] = mapped_column(BigInteger)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Referral(Base):
    __tablename__ = "referrals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, index=True)
    referred_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    cards_bonus: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_bonus: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProfileView(Base):
    __tablename__ = "profile_views"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    viewer_id: Mapped[int] = mapped_column(BigInteger)
    target_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Achievement(Base):
    __tablename__ = "achievements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    key: Mapped[str] = mapped_column(String(32))
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_user_ach"),)


class BotSetting(Base):
    __tablename__ = "bot_settings"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[str] = mapped_column(String(64), default="")
