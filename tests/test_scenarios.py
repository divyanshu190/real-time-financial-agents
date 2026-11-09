"""End-to-end scenario tests through the real Pathway engine (late-failure drills included)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pathway as pw                             # noqa: E402
from pathway.internals.parse_graph import G      # noqa: E402

from fa import run as runner                     # noqa: E402
from fa import simulator                         # noqa: E402


def _run(tmp_path, events, kill=None):
    G.clear()
    return runner.run(events=events, speed=0, out_dir=tmp_path, kill_switch=kill or (tmp_path / "NO_KILL"), quiet=True)


def test_three_ps_scenarios(tmp_path):
    recs, summary = _run(tmp_path, list(simulator.generate()))
    by = {r["customer_id"]: r for r in recs if r["status"].startswith("SENT") and r["customer_id"].startswith("C900")}
    assert by["C9001"]["action"] == "EXTRA_VERIFICATION"
    assert by["C9002"]["action"] in {"SAVINGS_OFFER", "PREAPPROVED_LOAN_OFFER"}
    assert by["C9003"]["action"] == "ASSIST_CALL_SCRIPT"
    for r in by.values():                      # grounded + cited + audited
        assert r["status"] == "SENT" and "[ref: e-" in r["message"] and r["trace"]
    assert (tmp_path / "metrics.json").exists()


def test_kill_switch_suppresses_actions(tmp_path):
    kill = tmp_path / "KILL"
    kill.write_text("1")
    recs, _ = _run(tmp_path, list(simulator.generate()), kill)
    assert recs and not any(r["status"].startswith("SENT") for r in recs)
    assert any(r["status"] == "SUPPRESSED_KILL_SWITCH" for r in recs)


def test_unknown_customer_and_odd_event_type_do_not_crash(tmp_path):
    ev = list(simulator.generate(5, 30))
    ev.append(dict(event_id="e-x1", customer_id="UNKNOWN", event_type="???", channel="x", amount=5.0,
                   country="IN", merchant="", ts=99999.0))
    recs, _ = _run(tmp_path, ev)
    assert any(r["customer_id"] == "UNKNOWN" for r in recs)
