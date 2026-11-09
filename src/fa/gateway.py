"""Action gateway: consumes Pathway decision updates, runs agent + guardrails, writes the audit log,
and records event -> decision -> action latency. Idempotent per (customer, last_event_id)."""
import json
import statistics
import threading
import time as _time

from . import config, guardrails
from .agent import run_agent
from .personalize import build_message, summary3


class Gateway:
    def __init__(self, out_dir=None, kill_switch=None):
        self.out_dir = out_dir or config.OUT_DIR
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.kill = kill_switch or config.KILL_SWITCH_FILE
        self.seen: set[tuple] = set()
        self.records: list[dict] = []
        self.lock = threading.Lock()
        self.f = open(self.out_dir / "actions.jsonl", "w")

    # signature expected by pw.io.subscribe
    def on_change(self, key, row, time, is_addition):
        if not is_addition:
            return
        t_decision = _time.time()
        k = (row["customer_id"], row["last_event_id"])
        with self.lock:
            if k in self.seen:
                return
            self.seen.add(k)
        d = json.loads(row["decision"])
        facts = [tuple(f) for f in row["facts"]] if row["facts"] else []
        rec = {"customer_id": row["customer_id"], "event_id": row["last_event_id"], "trigger": d["trigger"],
               "action": d["action"], "score": d["score"], "reasons": d["reasons"],
               "signals": {"p_churn": round(row["p_churn"], 3), "p_offer": round(row["p_offer"], 3),
                           "p_life": round(row["p_life"], 3), "anomaly": round(row["last_anomaly"], 3)},
               "event_wall": row["emit_wall"], "decision_wall": t_decision, "status": "NO_ACTION"}
        if d["trigger"] != "NONE" and d["action"] != "NO_ACTION" and facts:
            self._act(rec, d, facts)
        rec["action_wall"] = _time.time()
        rec["event_to_decision_ms"] = round((t_decision - rec["event_wall"]) * 1e3, 2)
        rec["event_to_action_ms"] = round((rec["action_wall"] - rec["event_wall"]) * 1e3, 2)
        with self.lock:
            self.records.append(rec)
            self.f.write(json.dumps(rec) + "\n")
            self.f.flush()

    def _act(self, rec, d, facts):
        if self.kill.exists():
            rec["status"] = "SUPPRESSED_KILL_SWITCH"
            return
        ctx, trace = run_agent(d["action"], rec["customer_id"], facts)
        msg, source = build_message(d["trigger"], d["action"], facts)
        ok, failed = guardrails.check(msg, d["trigger"], d["action"], facts)
        if not ok:
            rec["guardrail_failures"] = failed
            msg, source = guardrails.FALLBACK, "fallback"
        rec.update(status="SENT" if ok else "SENT_FALLBACK", message=guardrails.redact(msg), message_source=source,
                   summary=summary3(d["trigger"], d["action"], facts, d["reasons"]), trace=trace.steps)

    def close(self):
        self.f.close()
        acts = [r for r in self.records if r["status"].startswith("SENT")]
        lat = [r["event_to_action_ms"] for r in self.records]
        pct = lambda xs, q: round(sorted(xs)[min(len(xs) - 1, int(q * len(xs)))], 2) if xs else None
        summary = {
            "decisions": len(self.records), "actions": len(acts),
            "by_trigger": {t: sum(1 for r in self.records if r["trigger"] == t)
                           for t in sorted({r["trigger"] for r in self.records})},
            "event_to_action_ms": {"p50": pct(lat, .5), "p95": pct(lat, .95), "max": max(lat) if lat else None,
                                   "mean": round(statistics.mean(lat), 2) if lat else None},
            "note": "latency includes Pathway minibatch scheduling + per-event ML scoring on one process",
        }
        (self.out_dir / "metrics.json").write_text(json.dumps(summary, indent=2))
        return summary
