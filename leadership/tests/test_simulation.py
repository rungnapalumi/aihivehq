"""Tests for the deterministic Leadership Expedition simulation engine (site/leadership/assets/sim.js)."""
import json
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SIM_JS = HERE.parent.parent / "site" / "leadership" / "assets" / "sim.js"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is required to run the JS simulation engine")


def node(cmd: dict) -> dict:
    out = subprocess.run([NODE, str(HERE / "sim_harness.js"), json.dumps(cmd)], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout)


@pytest.fixture(scope="module")
def runs():
    return node({"op": "all"})["runs"]


def test_engine_has_no_randomness_or_clock():
    src = SIM_JS.read_text(encoding="utf-8")
    assert "Math.random" not in src
    assert not re.search(r"\bDate\b", src)
    assert "fetch(" not in src and "XMLHttpRequest" not in src


def test_four_decisions_with_three_options_each():
    meta = node({"op": "meta"})
    assert [d["id"] for d in meta["decisions"]] == ["d1", "d2", "d3", "d4"]
    for d in meta["decisions"]:
        assert len(d["options"]) == 3
        for o in d["options"]:
            assert o["tradeoff"], "every option must state its trade-off"
    assert [d["label"] for d in meta["dimensions"]] == [
        "Strategic Thinking", "Decision Making", "Adaptability", "Delegation", "Communication", "Execution"]


def test_map_has_start_finish_and_five_checkpoints():
    meta = node({"op": "meta"})
    assert set(meta["map"]["checkpoints"]) == {"CP1", "CP2", "CP3", "CP4", "CP5"}
    assert "start" in meta["map"] and "finish" in meta["map"]
    assert len(meta["map"]["routes"]) == 3
    assert len({c["points"] for c in meta["map"]["checkpoints"].values()}) == 5  # different rewards


def test_same_choices_give_identical_state_and_report():
    cmd = {"op": "run", "choices": ["scout", "specialists", "huddle", "nearest"], "rationales": ["Information first, please.", "", "", ""]}
    assert node(cmd) == node(cmd)


def test_every_path_completes_with_valid_report(runs):
    assert len(runs) == 81
    for r in runs:
        s, rep = r["state"], r["report"]
        assert s["finished"] and len(s["decisions"]) == 4
        assert len(rep["dimensions"]) == 6
        assert all(0 <= d["score"] <= 100 for d in rep["dimensions"])
        assert len(rep["history"]) == 4 and len(rep["alternatives"]) == 4 and len(rep["reflections"]) == 4
        assert len(rep["plan"]) == 4 and len(rep["strengths"]) == 2 and len(rep["development"]) == 2
        assert "illustrative simulation indicators" in rep["disclaimer"]
        assert "not a validated assessment" in rep["disclaimer"]


def test_different_decisions_produce_different_outcomes(runs):
    outcomes = {(r["state"]["points"], r["state"]["timeRemaining"], r["state"]["energy"], tuple(r["state"]["checkpoints"])) for r in runs}
    profiles = {tuple(d["score"] for d in r["report"]["dimensions"]) for r in runs}
    assert len(outcomes) >= 40
    assert len(profiles) == 81


def test_no_option_is_always_best(runs):
    """For each decision, every option maximises mission points in at least one context."""
    for k in range(4):
        best = defaultdict(int)
        groups = defaultdict(list)
        for r in runs:
            key = tuple(c for j, c in enumerate(r["choices"]) if j != k)
            groups[key].append(r)
        for g in groups.values():
            top = max(x["state"]["points"] for x in g)
            for x in g:
                if x["state"]["points"] == top:
                    best[x["choices"][k]] += 1
        assert len(best) == 3, f"decision {k + 1}: some option is never the best choice: {dict(best)}"


def test_tracks_time_resources_checkpoints_points_and_rationale():
    out = node({"op": "run", "choices": ["valley", "rotate", "replan", "finish"], "rationales": ["Keep the team fresh for later.", "", "", ""]})
    s = out["state"]
    assert s["timeRemaining"] < 125 and s["energy"] < 100 and s["supplies"] == 2
    assert s["checkpoints"] == ["CP1", "CP3"]
    assert s["decisions"][0]["rationale"] == "Keep the team fresh for later."
    assert [d["label"] for d in s["decisions"]] == ["Valley Trail", "Rotate leadership", "Re-plan on a safer line", "Head to the finish"]


def test_rationale_is_scored_transparently():
    base = node({"op": "run", "choices": ["valley", "rotate", "replan", "finish"]})["report"]
    withr = node({"op": "run", "choices": ["valley", "rotate", "replan", "finish"], "rationales": ["A considered reason for this.", "", "", ""]})["report"]
    score = lambda rep, label: next(d["score"] for d in rep["dimensions"] if d["label"] == label)
    assert score(withr, "Communication") == score(base, "Communication") + 3
    assert score(withr, "Decision Making") == score(base, "Decision Making") + 2
    assert any(c["source"] == "Decision 1 · rationale" for c in withr["contributions"])


def test_report_scores_equal_baseline_plus_listed_contributions(runs):
    for r in runs[:: 7]:
        rep = r["report"]
        for d in rep["dimensions"]:
            total = rep["baseline"] + sum(c["delta"] for c in rep["contributions"] if c["dimension"] == d["label"])
            assert d["score"] == max(0, min(100, total))


def test_report_mentions_only_recorded_choices(runs):
    meta = node({"op": "meta"})
    all_labels = {o["label"] for d in meta["decisions"] for o in d["options"]}
    for r in runs[:: 5]:
        chosen = {h["choice"] for h in r["report"]["history"]}
        not_chosen = all_labels - chosen
        text = " ".join(r["report"]["patterns"] + [s["evidence"] for s in r["report"]["strengths"] + r["report"]["development"]])
        for label in not_chosen:
            assert f"D1 {label}" not in text and f"· {label}" not in text


def test_event_response_depends_on_earlier_choices():
    a = node({"op": "run", "choices": ["ridge", "command", "huddle", "finish"]})["state"]
    b = node({"op": "run", "choices": ["ridge", "specialists", "huddle", "finish"]})["state"]
    huddle_a = a["decisions"][2]["delta"]["time"]
    huddle_b = b["decisions"][2]["delta"]["time"]
    assert huddle_b > huddle_a  # roles mean the huddle costs less time (less negative delta)


def test_late_finish_is_penalised():
    s = node({"op": "run", "choices": ["ridge", "specialists", "push", "summit"]})["state"]
    assert s["late"] and s["lateMinutes"] > 0
    assert s["finishBonus"] == 0


def test_out_of_order_and_unknown_options_are_rejected():
    assert "out of order" in node({"op": "apply", "steps": [["d2", "command"]]})["error"]
    assert "Unknown option" in node({"op": "apply", "steps": [["d1", "teleport"]]})["error"]
    assert "not finished" in node({"op": "unfinished"})["error"]
