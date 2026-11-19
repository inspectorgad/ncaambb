import datetime as dt
import json

import pandas as pd
import pytest

from ncaambb import pipeline
from ncaambb.fetching import FetchError, fetch_bytes
from ncaambb.schema import to_long

TODAY = dt.date(2026, 11, 18)


def make_paths(tmp_path):
    return pipeline.Paths(cache=tmp_path / "cache", site_data=tmp_path / "site", raw=None)


def copy_fixtures(src, dst, drop=()):
    dst.mkdir()
    for f in src.iterdir():
        if not any(f.name.startswith(d) for d in drop):
            (dst / f.name).write_bytes(f.read_bytes())
    return dst


def test_offline_run(fixtures_dir, tmp_path):
    paths = make_paths(tmp_path)
    table, statuses = pipeline.run(fixtures=fixtures_dir, paths=paths, today=TODAY)
    status = {s.source: s.status for s in statuses}
    assert status == {
        "torvik": "ok", "haslametrics": "ok", "espn_bpi": "ok", "teamrankings": "ok",
        "cbbd": "ok", "bracketmatrix": "ok",
        # saved NET pages are last season's: skipped, not failed
        "warrennolan": "not_current", "ncaa_net": "not_current",
    }
    assert len(table) == 365
    assert (table["pred_n"] >= 4).all() and (table["pred_n"] == 5).sum() == 364
    assert (table["res_n"] == 2).all()

    latest = json.loads((paths.site_data / "latest.json").read_text())
    assert latest["as_of"] == "2026-11-18" and len(latest["teams"]) == 365
    top = latest["teams"][0]
    assert top["pred"]["rank"] == 1
    assert set(top["stats"]) == {"adj_em", "adj_o", "adj_d", "tempo", "sos"}
    assert {"torvik", "haslametrics", "espn_bpi", "teamrankings", "cbbd", "bracketmatrix"} == set(top["sources"])
    assert not any(k.startswith("espn_") for t in latest["teams"] for k in t["sources"].get("espn_bpi", {}))

    kansas = json.loads((paths.site_data / "team" / "kansas.json").read_text())
    assert kansas["games_played"] == 4 and len(kansas["four_factors"]) == 4
    assert len(list((paths.site_data / "team").glob("*.json"))) == 365

    meta = json.loads((paths.site_data / "meta.json").read_text())
    assert meta["team_details"]["status"] == "ok"
    assert meta["players"]["status"] == "ok" and meta["players"]["torvik"] == "ok"
    assert len(json.loads((paths.site_data / "players.json").read_text())["top"]) == 50
    assert "players" in json.loads((paths.site_data / "team" / "kansas.json").read_text())
    assert meta["weights"]["trim_min_inputs"] == 4
    history = json.loads((paths.site_data / "history" / "2026-11-18.json").read_text())
    assert history["fields"][0] == "pred_rank" and len(history["teams"]) == 365
    assert json.loads((paths.site_data / "history" / "index.json").read_text()) == ["2026-11-18"]
    assert (paths.cache / "torvik.csv").exists()
    assert not (paths.cache / "ncaa_net.csv").exists()


def test_broken_source_falls_back_to_recent_cache(fixtures_dir, tmp_path):
    paths = make_paths(tmp_path)
    pipeline.run(fixtures=fixtures_dir, paths=paths, today=TODAY)  # fills the cache

    broken = copy_fixtures(fixtures_dir, tmp_path / "fx", drop=("torvik",))
    (broken / "torvik_broken.csv").write_text("rank,team\n1,Kansas\n")
    _, statuses = pipeline.run(fixtures=broken, paths=paths, today=TODAY + dt.timedelta(days=2))
    torvik = next(s for s in statuses if s.source == "torvik")
    assert torvik.status == "stale" and torvik.data_date == "2026-11-18"
    assert "missing columns" in torvik.error

    # too old: dropped instead
    _, statuses = pipeline.run(fixtures=broken, paths=paths, today=TODAY + dt.timedelta(days=4))
    assert next(s for s in statuses if s.source == "torvik").status == "failed"


def test_main_exit_code(fixtures_dir, tmp_path, monkeypatch):
    paths = make_paths(tmp_path)
    monkeypatch.setattr(pipeline, "Paths", lambda: paths)
    assert pipeline.main(["--fixtures", str(fixtures_dir), "--date", "2026-11-18"]) == 0
    broken = copy_fixtures(fixtures_dir, tmp_path / "fx", drop=("torvik", "haslametrics", "espn_bpi"))
    for name in ("torvik", "haslametrics", "espn_bpi"):
        (broken / f"{name}_broken.txt").write_text("nothing useful")
    # same cache dir => these three go stale, which still counts toward the failure limit
    assert pipeline.main(["--fixtures", str(broken), "--date", "2026-11-19"]) == 1


def test_bot_check_page_is_a_fetch_error():
    class Resp:
        content = b"<html><title>Just a moment...</title></html>"

        def raise_for_status(self):
            pass

    class Session:
        def get(self, url, timeout, headers=None):
            return Resp()

    with pytest.raises(FetchError, match="bot check"):
        fetch_bytes("https://example.com", Session())


def test_to_long_keeps_rank_only_metrics():
    wide = pd.DataFrame({"team_id": ["a"], "source_name": ["A"], "rating": [5.0],
                         "rating_rank": [1], "sor_rank": [7]})
    long = to_long(wide, "x", "2026-11-18").set_index("metric")
    assert long.loc["rating", "rank"] == 1
    assert long.loc["sor_rank", "value"] == 7


@pytest.mark.live
def test_live_sources(tmp_path):
    _, statuses = pipeline.run(paths=make_paths(tmp_path))
    assert [s.source for s in statuses if s.status not in ("ok", "not_current")] == []


def test_missing_api_key_is_not_a_failure(fixtures_dir, tmp_path, monkeypatch):
    """Live mode without CBBD_API_KEY: cbbd is 'not_configured', not 'failed'."""
    from ncaambb.fetching import NotConfigured
    from ncaambb.sources import REGISTRY

    def no_key(self, session=None):
        raise NotConfigured("CBBD_API_KEY is not set")

    monkeypatch.setattr(REGISTRY["cbbd"], "fetch", no_key)
    cfg = pipeline.load_sources_config(today=TODAY)
    cfg["sources"] = {"cbbd": cfg["sources"]["cbbd"]}
    _, statuses = pipeline.collect(cfg, pipeline.Crosswalk.load(), TODAY, make_paths(tmp_path))
    assert statuses[0].status == "not_configured"


def test_history_index_lists_only_dates_across_runs(fixtures_dir, tmp_path):
    """Regression: the second run used to add "index" itself to index.json."""
    paths = make_paths(tmp_path)
    pipeline.run(fixtures=fixtures_dir, paths=paths, today=TODAY)
    pipeline.run(fixtures=fixtures_dir, paths=paths, today=TODAY + dt.timedelta(days=1))
    index = json.loads((paths.site_data / "history" / "index.json").read_text())
    assert index == ["2026-11-18", "2026-11-19"]
