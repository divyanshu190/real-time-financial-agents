"""CLI entry point:  python -m fa.run --speed 20"""
import argparse
import json

import pathway as pw

from . import config, pipeline, simulator
from .gateway import Gateway


def run(events=None, speed=20.0, source="simulator", jsonl_dir=None, out_dir=None, kill_switch=None, quiet=False):
    out_dir = out_dir or config.OUT_DIR
    if source == "jsonl":   # watch a folder of *.jsonl event files (streaming, picks up new files)
        raw = pw.io.jsonlines.read(jsonl_dir, schema=simulator.RawEvent, mode="streaming")
    else:
        raw = simulator.read_stream(events, speed)
    E, D, M = pipeline.build(raw, pipeline.read_profiles())
    gw = Gateway(out_dir, kill_switch)
    pw.io.subscribe(D, on_change=gw.on_change)
    pw.io.jsonlines.write(M.select(*M), str(out_dir / "minute_metrics.jsonl"))
    pw.run(monitoring_level=pw.MonitoringLevel.NONE)
    summary = gw.close()
    if not quiet:
        print(json.dumps(summary, indent=2))
        for r in gw.records:
            if r["status"].startswith("SENT"):
                print(f"\n[{r['trigger']}] {r['customer_id']} -> {r['action']} ({r['event_to_action_ms']} ms)\n  {r['message']}")
    return gw.records, summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--speed", type=float, default=20.0, help="replay speed factor (0 = as fast as possible)")
    ap.add_argument("--source", choices=["simulator", "jsonl"], default="simulator")
    ap.add_argument("--jsonl-dir", default=str(config.DATA_DIR / "stream"))
    a = ap.parse_args()
    run(speed=a.speed, source=a.source, jsonl_dir=a.jsonl_dir)
