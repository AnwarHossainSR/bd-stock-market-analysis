from fastapi.testclient import TestClient

from app.main import app
from app.services import screen

client = TestClient(app)


def test_report_generates_pdf(monkeypatch):
    monkeypatch.setattr(screen.dse, "get_prices", lambda: [])
    r = client.get("/api/report?buy=2&watch=2").json()
    assert r["url"].startswith("/reports/") and r["file"].endswith(".pdf")
    resp = client.get(r["url"])
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
