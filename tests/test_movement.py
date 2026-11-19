import json

from ncaambb import movement

FIELDS = ["pred_rank", "res_rank", "pred_z", "res_z"]


def rec(tid, pred, res, gap=None, spread=0.1, seed=None):
    return {"id": tid, "pred": {"rank": pred}, "res": {"rank": res}, "gap": gap if gap is not None else pred - res,
            "spread": spread, "sources": {"bracketmatrix": {"consensus_seed": seed}} if seed else {}}


def snap(ranks, field=None):
    s = {"fields": FIELDS, "teams": {t: [p, r, 0, 0] for t, (p, r) in ranks.items()}}
    if field is not None:
        s["field"] = field
    return s


def test_no_history_degrades_gracefully():
    records = [rec("a", 1, 2), rec("b", 2, 1)]
    movement.add_movement(records, [], "2026-11-20")
    assert records[0]["move"]["pred"] is None and records[0]["move"]["since"] is None
    assert records[0]["trend"]["pred"] == [1]
    st = movement.stories(records, [])
    assert st["risers"] == [] and st["new_in_field"] == []
    assert st["under_rewarded"] == [{"id": "a", "value": -1}]


def test_day_and_week_movement_and_trend():
    history = [
        ("2026-11-10", snap({"a": (5, 9), "b": (1, 1)})),
        ("2026-11-12", snap({"a": (4, 8), "b": (2, 2)})),
        ("2026-11-19", snap({"a": (3, 7), "b": (1, 3)})),
    ]
    records = [rec("a", 1, 6), rec("b", 2, 2), rec("new", 3, 3)]
    movement.add_movement(records, history, "2026-11-20")
    a, b, new = records
    assert a["move"]["pred"] == 2 and a["move"]["res"] == 1          # 3 -> 1, 7 -> 6
    assert a["move"]["week_since"] == "2026-11-12" and a["move"]["pred_7d"] == 3   # 4 -> 1
    assert b["move"]["pred"] == -1
    assert new["move"]["pred"] is None                                # not in earlier snapshots
    assert a["trend"]["pred"] == [5, 4, 3, 1]
    assert a["trend"]["dates"][-1] == "2026-11-20"


def test_stories_pick_the_right_teams():
    history = [("2026-11-19", snap({"up": (40, 40), "down": (10, 10), "far": (300, 300), "steady": (5, 5)},
                                   field=["down", "steady"]))]
    records = [rec("up", 20, 30), rec("down", 25, 12, seed=None), rec("far", 200, 200),
               rec("steady", 5, 5, seed=1), rec("newbie", 30, 60, seed=11, spread=0.9)]
    movement.add_movement(records, history, "2026-11-20")
    st = movement.stories(records, history)
    assert [s["id"] for s in st["risers"]] == ["up"]          # "far" rose 100 but is outside the top 100
    assert st["risers"][0]["value"] == 20
    assert [s["id"] for s in st["fallers"]] == ["down"]
    assert st["disputed"][0]["id"] == "newbie"
    assert [s["id"] for s in st["new_in_field"]] == ["newbie"]
    assert [s["id"] for s in st["left_field"]] == ["down"]


def test_load_history_skips_index_today_and_bad_files(tmp_path):
    (tmp_path / "2026-11-18.json").write_text(json.dumps(snap({"a": (1, 1)})))
    (tmp_path / "2026-11-19.json").write_text("not json")
    (tmp_path / "2026-11-20.json").write_text(json.dumps(snap({"a": (2, 2)})))
    (tmp_path / "index.json").write_text("[]")
    assert [d for d, _ in movement.load_history(tmp_path, before="2026-11-20")] == ["2026-11-18"]
