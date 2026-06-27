from fastapi.testclient import TestClient

from api.main import app
from api.routers import reports


def test_reports_list_only_pdf_and_md(monkeypatch, tmp_path):
    (tmp_path / "a.pdf").write_text("pdf", encoding="utf-8")
    (tmp_path / "b.md").write_text("md", encoding="utf-8")
    (tmp_path / "ignore.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(reports, "REPORTS_DIR", str(tmp_path))

    client = TestClient(app)
    response = client.get("/api/reports")

    assert response.status_code == 200
    names = {x["file"] for x in response.json()["reports"]}
    assert names == {"a.pdf", "b.md"}
