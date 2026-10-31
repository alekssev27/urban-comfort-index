"""Account operations for Mesto."""

import re

import bcrypt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.database import User, UserPreferences, session_scope


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegistrationError(ValueError):
    """Raised when registration data is invalid or already used."""


def validate_registration(name: str, email: str, password: str) -> tuple[str, str]:
    name = name.strip()
    email = email.strip().lower()

    if not name or len(name) > 80:
        raise RegistrationError("Имя должно содержать от 1 до 80 символов.")
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        raise RegistrationError("Введите корректный адрес электронной почты.")
    if len(password) < 8:
        raise RegistrationError("Пароль должен содержать не менее 8 символов.")
    if len(password.encode("utf-8")) > 72:
        raise RegistrationError("Пароль слишком длинный (максимум 72 байта).")
    return name, email


def register_user(name: str, email: str, password: str, profile: str) -> int:
    """Create an account and its initial preferences; return the new user ID."""
    name, email = validate_registration(name, email, password)
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

    try:
        with session_scope() as session:
            existing = session.scalar(select(User.id).where(User.email == email))
            if existing is not None:
                raise RegistrationError("Аккаунт с такой почтой уже существует.")

            user = User(name=name, email=email, password_hash=password_hash)
            user.preferences = UserPreferences(profile=profile)
            session.add(user)
            session.flush()
            return user.id
    except IntegrityError as error:
        raise RegistrationError("Аккаунт с такой почтой уже существует.") from error


def authenticate_user(email: str, password: str) -> dict | None:
    """Verify credentials and return only non-sensitive account fields."""
    email = email.strip().lower()
    with session_scope() as session:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            return None
        try:
            valid = bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8"))
        except (ValueError, TypeError):
            valid = False
        if not valid:
            return None

        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "profile": user.preferences.profile if user.preferences else "Студент",
            "created_at": user.created_at,
        }


def get_user_account(user_id: int) -> dict | None:
    """Load editable account data without exposing the password hash."""
    with session_scope() as session:
        user = session.get(User, user_id)
        if user is None:
            return None
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "profile": user.preferences.profile if user.preferences else "Студент",
            "created_at": user.created_at,
        }


def update_user_account(user_id: int, name: str, profile: str) -> None:
    """Update the account name and life-scenario preference."""
    name = name.strip()
    if not name or len(name) > 80:
        raise RegistrationError("Имя должно содержать от 1 до 80 символов.")
    if profile not in {"Студент", "Пара", "Семья с детьми"}:
        raise RegistrationError("Выберите доступный жизненный сценарий.")

    with session_scope() as session:
        user = session.get(User, user_id)
        if user is None:
            raise RegistrationError("Пользователь не найден.")
        user.name = name
        if user.preferences is None:
            user.preferences = UserPreferences(profile=profile)
        else:
            user.preferences.profile = profile
