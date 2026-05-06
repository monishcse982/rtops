from os import getenv
from time import sleep

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import logger


def _get_bool_env(name: str, default: bool) -> bool:
    raw_value = getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(name: str, default: int) -> int:
    raw_value = getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


DATABASE_URL = getenv("DATABASE_URL", "postgresql://user:password@localhost/orders_db")
DB_CONNECT_MAX_RETRIES = _get_int_env("DB_CONNECT_MAX_RETRIES", 5)
DB_CONNECT_RETRY_DELAY_SECONDS = _get_int_env("DB_CONNECT_RETRY_DELAY_SECONDS", 5)
DB_CONNECT_CHECK_ON_STARTUP = _get_bool_env("DB_CONNECT_CHECK_ON_STARTUP", True)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def ensure_database_connection(
    max_retries: int = DB_CONNECT_MAX_RETRIES,
    retry_delay_seconds: int = DB_CONNECT_RETRY_DELAY_SECONDS,
) -> None:
    if max_retries < 1:
        max_retries = 1

    for i in range(max_retries):
        try:
            with engine.connect():
                logger.info("Database connection established")
            return
        except OperationalError as exc:
            is_last_attempt = i == max_retries - 1
            if is_last_attempt:
                break
            logger.warning(f"Database not ready, retrying ({i + 1}/{max_retries}): {exc}")
            if retry_delay_seconds > 0:
                sleep(retry_delay_seconds)

    raise OperationalError(
        statement=None,
        params=None,
        orig=RuntimeError("Could not connect to the database after startup retries"),
    )


# Dependency to get a DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
