import datetime as dt

import pytest

from ncaambb import season
from ncaambb.config import in_active_window, load_sources_config, season_for


@pytest.mark.parametrize(
    "day, expected",
    [("2026-07-31", 2026), ("2026-08-01", 2027), ("2026-11-18", 2027), ("2027-04-06", 2027)],
)
def test_season_for(day, expected):
    assert season_for(dt.date.fromisoformat(day)) == expected


def test_auto_season_in_config():
    cfg = load_sources_config(today=dt.date(2027, 12, 1))
    assert cfg["season"] == 2028


@pytest.mark.parametrize(
    "day, active",
    [("2026-11-01", True), ("2026-12-31", True), ("2027-01-01", True), ("2027-04-15", True),
     ("2027-04-16", False), ("2027-08-01", False), ("2026-10-31", False)],
)
def test_active_window_wraps_new_year(day, active):
    cfg = {"active_window": {"start": "11-01", "end": "04-15"}}
    assert in_active_window(cfg, dt.date.fromisoformat(day)) is active


def test_season_cli_writes_github_output(tmp_path, monkeypatch, capsys):
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    season.main(["--date", "2027-07-01", "--github-output"])
    assert out.read_text() == "active=false\n"
    assert "season 2027" in capsys.readouterr().out
