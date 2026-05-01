import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient


TEST_DB_PATH = Path("/private/tmp/rtops_test.sqlite3")
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

from app.main import app  # noqa: E402
from app.models.database import Base, SessionLocal, engine  # noqa: E402
from app.models import line_item_model, order_model, outbox_event_model, product_model  # noqa: F401,E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    SessionLocal.remove() if hasattr(SessionLocal, "remove") else None


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
