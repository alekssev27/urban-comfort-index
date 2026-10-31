"""PostgreSQL connection, SQLAlchemy models, and session management for Mesto."""

import os
from contextlib import contextmanager

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("length(email) <= 254", name="ck_users_email_length"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    preferences: Mapped["UserPreferences"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)
    favorites: Mapped[list["Favorite"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    profile: Mapped[str] = mapped_column(String(40), nullable=False, default="Студент")
    weights_json: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    user: Mapped[User] = relationship(back_populates="preferences")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "cell_id", name="uq_favorites_user_cell"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    cell_id: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    comfort_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="user", cascade="all, delete-orphan")


def _database_url() -> str:
    """Read the database URL from environment variables or Streamlit secrets."""
    url = os.getenv("DATABASE_URL", "").strip()

    if not url:
        try:
            import streamlit as st

            url = str(st.secrets.get("DATABASE_URL", "")).strip()
        except Exception:
            url = ""

    if not url:
        raise RuntimeError(
            "Не задан DATABASE_URL. Добавьте строку подключения PostgreSQL "
            "в переменные окружения или Streamlit Secrets."
        )

    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(_database_url(), pool_pre_ping=True, pool_recycle=1800)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


@contextmanager
def session_scope():
    get_engine()
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database() -> None:
    """Create missing tables. Use migrations for future schema changes."""
    Base.metadata.create_all(get_engine())
