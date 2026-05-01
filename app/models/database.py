from os import getenv
from time import sleep

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import logger

# Load database URL from environment variable
DATABASE_URL = getenv("DATABASE_URL", "postgresql://user:password@localhost/orders_db")


MAX_RETRIES = 5
engine = create_engine(DATABASE_URL)

for i in range(MAX_RETRIES):
    try:
        with engine.connect():
            logger.info("Database connection established")
        break
    except OperationalError as exc:
        logger.warning(f"Database not ready, retrying ({i + 1}/{MAX_RETRIES}): {exc}")
        sleep(5)
else:
    raise OperationalError(
        statement=None,
        params=None,
        orig=RuntimeError("Could not connect to the database after startup retries"),
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


# Dependency to get a DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
