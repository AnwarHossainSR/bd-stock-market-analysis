from pathlib import Path

import history

FX = Path(__file__).parent / "fixtures"


def test_parse_archive_rows():
    rows = history.parse_archive((FX / "archive_gp.html").read_text(encoding="utf-8"))
    assert len(rows) >= 5
    r = rows[0]
    assert {"date", "code", "close", "high", "low", "volume"} <= r.keys()
    assert r["code"]
    assert all(isinstance(x["close"], (float, type(None))) for x in rows)
