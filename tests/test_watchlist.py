import watchlist


def test_write_watchlist(tmp_path):
    rows = [{"code": "ABC", "entry_below": 10, "breakout_above": 12, "stop": 9, "notes": "auto"}]
    out = watchlist.write_watchlist(rows, tmp_path / "watchlist.csv")

    text = out.read_text(encoding="utf-8")
    assert "code,entry_below,breakout_above,stop,notes" in text
    assert "ABC,10,12,9,auto" in text
