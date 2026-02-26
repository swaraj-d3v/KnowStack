import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:2233@localhost:5432/knowstack")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("ALLOW_DEV_AUTH", "true")

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
