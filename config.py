import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "sim", "s", "on"}


def _int_env(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


class Config:
    """Application configuration sourced exclusively from environment variables."""

    APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
    IS_PRODUCTION = APP_ENV == "production"
    DEBUG = _bool_env("FLASK_DEBUG", False)
    TESTING = _bool_env("TESTING", False)

    SECRET_KEY = os.getenv("SECRET_KEY", "")
    SECRET_PLACEHOLDERS = {"generate-a-random-value-before-running", "development-only-secret-key-change-me-123456789"}
    if not IS_PRODUCTION and (not SECRET_KEY or SECRET_KEY in SECRET_PLACEHOLDERS):
        SECRET_KEY = secrets.token_hex(32)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", IS_PRODUCTION)
    SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "ohmycoin_session")
    PERMANENT_SESSION_LIFETIME = timedelta(hours=_int_env("SESSION_HOURS", 8, minimum=1, maximum=24))
    SESSION_REFRESH_EACH_REQUEST = True

    MAX_CONTENT_LENGTH = _int_env("MAX_CONTENT_LENGTH_MB", 2, minimum=1, maximum=20) * 1024 * 1024

    LOGIN_MAX_ATTEMPTS = _int_env("LOGIN_MAX_ATTEMPTS", 5, minimum=3, maximum=20)
    LOGIN_WINDOW_MINUTES = _int_env("LOGIN_WINDOW_MINUTES", 15, minimum=1, maximum=1440)
    LOGIN_LOCKOUT_MINUTES = _int_env("LOGIN_LOCKOUT_MINUTES", 15, minimum=1, maximum=1440)
    PASSWORD_MIN_LENGTH = _int_env("PASSWORD_MIN_LENGTH", 10, minimum=8, maximum=128)

    ENABLE_SECURITY_HEADERS = _bool_env("ENABLE_SECURITY_HEADERS", True)
    TRUST_PROXY_HEADERS = _bool_env("TRUST_PROXY_HEADERS", False)
    ALLOW_REGISTRATION = _bool_env("ALLOW_REGISTRATION", True)

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = _int_env("DB_PORT", 3306, minimum=1, maximum=65535)
    DB_USER = os.getenv("DB_USER", "ohmycoin_app")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "ohmycoin")
    DB_CONNECTION_TIMEOUT = _int_env("DB_CONNECTION_TIMEOUT", 10, minimum=1, maximum=60)

    DB_CONFIG = {
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
        "host": DB_HOST,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "database": DB_NAME,
        "port": DB_PORT,
        "autocommit": False,
        "connection_timeout": DB_CONNECTION_TIMEOUT,
    }

    @classmethod
    def validate_security(cls) -> None:
        if cls.SESSION_COOKIE_SAMESITE not in {"Lax", "Strict", "None"}:
            raise RuntimeError("SESSION_COOKIE_SAMESITE deve ser Lax, Strict ou None.")

        if cls.IS_PRODUCTION:
            if cls.DEBUG or cls.TESTING:
                raise RuntimeError("DEBUG e TESTING devem estar desativados em produção.")
            if len(cls.SECRET_KEY) < 32 or cls.SECRET_KEY in cls.SECRET_PLACEHOLDERS:
                raise RuntimeError("SECRET_KEY ausente ou curta. Use pelo menos 32 caracteres aleatórios em produção.")
            if not cls.SESSION_COOKIE_SECURE:
                raise RuntimeError("SESSION_COOKIE_SECURE precisa estar ativo em produção.")
            if cls.SESSION_COOKIE_SAMESITE == "None" and not cls.SESSION_COOKIE_SECURE:
                raise RuntimeError("SameSite=None exige cookie Secure.")
            if not cls.DB_PASSWORD:
                raise RuntimeError("DB_PASSWORD não pode estar vazio em produção.")
