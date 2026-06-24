import os

# Set a dummy DB URL before importing the app so engine creation succeeds
# (no real connection is made for the liveness probe).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test")

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
