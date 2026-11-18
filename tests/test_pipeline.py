import json

import pandas as pd
import pytest

from ncaambb import pipeline
from ncaambb.fetching import FetchError, fetch_bytes


def test_offline_run(fixtures_dir, tmp_path):
    long, statuses = pipeline.run(fixtures=fixtures_dir, out_dir=tmp_path, as_of="2026-11-18")
    assert all(s.ok for s in statuses)
    assert long.groupby("source")["team_id"].nunique().to_dict() == {
        "espn_bpi": 365,
        "haslametrics": 365,
        "torvik": 365,
    }
    assert not long["metric"].str.startswith("espn_").any()
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["as_of"] == "2026-11-18"
    assert len(pd.read_csv(tmp_path / "metrics_long.csv")) == len(long)


def test_one_broken_source_does_not_stop_others(fixtures_dir, tmp_path):
    broken = tmp_path / "fx"
    broken.mkdir()
    for f in fixtures_dir.iterdir():
        (broken / f.name).write_bytes(f.read_bytes())
    (broken / "torvik_2027_team_results.csv.gz").unlink()
    (broken / "torvik_broken.csv").write_text("rank,team\n1,Kansas\n")
    long, statuses = pipeline.run(fixtures=broken, out_dir=tmp_path / "out")
    by_name = {s.source: s for s in statuses}
    assert not by_name["torvik"].ok and "missing columns" in by_name["torvik"].error
    assert by_name["haslametrics"].ok and by_name["espn_bpi"].ok
    assert set(long["source"]) == {"haslametrics", "espn_bpi"}


def test_bot_check_page_is_a_fetch_error(monkeypatch):
    class Resp:
        content = b"<html><title>Just a moment...</title></html>"

        def raise_for_status(self):
            pass

    class Session:
        def get(self, url, timeout):
            return Resp()

    with pytest.raises(FetchError, match="bot check"):
        fetch_bytes("https://example.com", Session())


@pytest.mark.live
def test_live_sources(tmp_path):
    _, statuses = pipeline.run(out_dir=tmp_path, raw_dir=None)
    assert [s.source for s in statuses if not s.ok] == []
