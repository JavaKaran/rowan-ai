import os
from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr
from sqlalchemy import URL
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger
from app.exceptions import EncryptionKeyMissing

logger = get_logger(__name__)


class DatabaseConnectionURLInput(Protocol):
    database_type: str
    username: str
    password: SecretStr | str
    host: str
    port: int
    database_name: str
    ssl_mode: str | None


def build_database_url(connection: DatabaseConnectionURLInput) -> URL:
    drivername = {
        "postgresql": "postgresql+psycopg2",
        "mysql": "mysql+pymysql",
    }[connection.database_type]

    query = {}
    if connection.database_type == "postgresql" and connection.ssl_mode:
        query["sslmode"] = connection.ssl_mode

    return URL.create(
        drivername=drivername,
        username=connection.username,
        password=_get_password_value(connection.password),
        host=connection.host,
        port=connection.port,
        database=connection.database_name,
        query=query,
    )


def build_connect_args(database_type: str) -> dict:
    if database_type == "postgresql":
        return {"connect_timeout": 5}

    if database_type == "mysql":
        return {"connect_timeout": 5}

    return {}


def encrypt_password(password: str) -> str:
    key = _get_encryption_key()

    try:
        return Fernet(key.encode()).encrypt(password.encode()).decode()
    except (ValueError, InvalidToken) as exc:
        logger.error("database_connection.encryption_key_invalid")
        raise EncryptionKeyMissing() from exc


def decrypt_password(encrypted_password: str) -> str:
    key = _get_encryption_key()

    try:
        return Fernet(key.encode()).decrypt(encrypted_password.encode()).decode()
    except (ValueError, InvalidToken) as exc:
        logger.error("database_connection.encryption_key_invalid")
        raise EncryptionKeyMissing() from exc


def format_database_error(exc: Exception) -> str:
    if isinstance(exc, SQLAlchemyError) and getattr(exc, "orig", None):
        return str(exc.orig).splitlines()[0]

    return str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__


def _get_password_value(password: SecretStr | str) -> str:
    if isinstance(password, SecretStr):
        return password.get_secret_value()

    return password


def _get_encryption_key() -> str:
    key = os.getenv("DATABASE_CONNECTION_ENCRYPTION_KEY")
    if not key:
        logger.error("database_connection.encryption_key_missing")
        raise EncryptionKeyMissing()

    return key
