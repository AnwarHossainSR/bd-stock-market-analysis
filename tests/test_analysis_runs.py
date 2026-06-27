import analysis_runs


def test_save_list_latest_and_commentary(tmp_path):
    payload = {
        "fetched_at": "2026-06-28T11:00:00+06:00",
        "market": {"regime": "MIXED", "breadth": {"adv": 1, "dec": 1, "value_mn": 10}},
        "screen": {"buy": [{"code": "ABC", "pct": 2}], "watch": [], "avoid": []},
        "report": {"file": "x.pdf", "url": "/reports/x.pdf"},
        "disclaimer": analysis_runs.DISCLAIMER,
    }

    record = analysis_runs.save_run(payload, runs_dir=tmp_path)
    listed = analysis_runs.list_runs(runs_dir=tmp_path)
    latest = analysis_runs.latest_run(runs_dir=tmp_path)
    updated = analysis_runs.save_commentary(record["id"], "codex notes", runs_dir=tmp_path)

    assert listed[0]["id"] == record["id"]
    assert latest["id"] == record["id"]
    assert updated["commentary_md"] == "codex notes"


def test_get_run_missing_returns_none(tmp_path):
    assert analysis_runs.get_run("missing", runs_dir=tmp_path) is None
