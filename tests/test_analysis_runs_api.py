from fastapi.testclient import TestClient

from api.main import app
from api.routers import analysis


def _payload(pdf=True):
    payload = {
        "fetched_at": "2026-06-28T11:00:00+06:00",
        "market": {"regime": "MIXED", "breadth": {"adv": 1, "dec": 1, "value_mn": 10}},
        "screen": {"buy": [], "watch": [], "avoid": []},
        "portfolio": None,
        "session": {"market_state": "LIVE"},
        "disclaimer": "Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice.",
    }
    if pdf:
        payload["report"] = {"file": "x.pdf", "url": "/reports/x.pdf"}
    return payload


def test_create_and_fetch_analysis_run(monkeypatch, tmp_path):
    monkeypatch.setattr(analysis, "_analysis_payload", lambda **kwargs: _payload(pdf=kwargs.get("pdf", True)))
    monkeypatch.setattr(analysis.analysis_runs, "RUNS_DIR", tmp_path)
    client = TestClient(app)

    created = client.post("/api/analysis/runs").json()
    listed = client.get("/api/analysis/runs").json()
    latest = client.get("/api/analysis/runs/latest").json()
    commented = client.post(f"/api/analysis/runs/{created['id']}/commentary", json={"commentary_md": "notes"}).json()

    assert created["report_status"] == "ok"
    assert listed["runs"][0]["id"] == created["id"]
    assert latest["id"] == created["id"]
    assert commented["commentary_md"] == "notes"
