from datetime import datetime

from app.services import pdf


def test_build_pdf_writes_valid_file():
    data = {"regime": "MIXED",
            "breadth": {"adv": 1, "dec": 1, "total": 2, "value_mn": 10.0},
            "buy": [], "watch": [], "avoid": []}
    p = pdf.build_pdf(data, datetime(2026, 6, 26, 17, 30))
    assert p.exists()
    assert p.read_bytes()[:4] == b"%PDF"
    assert "DSE_Analysis_2026-06-26_1730" in p.name
