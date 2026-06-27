import os

import charts
import indicators as ind


def test_price_chart_png(tmp_path):
    h = [{"date": f"d{i}", "close": 100 + i, "high": 101 + i, "low": 99 + i, "volume": 100} for i in range(60)]
    p = tmp_path / "c.png"
    charts.price_chart(h, ind.compute(h), str(p))
    assert os.path.getsize(p) > 1000


def test_sector_pie_png(tmp_path):
    p = tmp_path / "s.png"
    charts.sector_pie({"Textile": 3, "Bank": 2}, str(p))
    assert os.path.getsize(p) > 1000
