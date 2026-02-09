from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_healthz_ok():
    r = client.get("/healthz")
    assert r.status_code == 200

def test_readyz_ok():
    r = client.get("/readyz")
    assert r.status_code == 200

def test_headers_present():
    r = client.get("/healthz")
    assert "x-request-id" in {k.lower(): v for k, v in r.headers.items()}
    assert "x-trace-id" in {k.lower(): v for k, v in r.headers.items()}
