"""Event simulator + Pathway custom Python connector.

Generates a realistic mixed stream (background customers + 3 scripted PS scenarios)
and replays it with a speed factor. Also usable as a plain generator for tests.
"""
import random
import time
import uuid
from typing import Iterator

import pathway as pw

from .schema import RawEvent

COUNTRIES = ["IN"] * 9 + ["US", "AE"]
MERCHANTS = ["grocer", "fuel", "ecom", "telecom", "dining", "travel"]

SCENARIO_CUSTOMERS = {
    "risky_transfer": "C9001",
    "large_deposit": "C9002",
    "card_decline": "C9003",
}


def customer_ids(n: int) -> list[str]:
    return [f"C{1000 + i}" for i in range(n)]


def _ev(cid, etype, amount, ts, country="IN", merchant="", channel="app"):
    return dict(event_id=f"e-{uuid.uuid4().hex[:10]}", customer_id=cid, event_type=etype,
                channel=channel, amount=float(amount), country=country, merchant=merchant, ts=float(ts))


def generate(n_customers: int = 30, n_background: int = 400, seed: int = 7) -> Iterator[dict]:
    rng = random.Random(seed)
    ids = customer_ids(n_customers)
    t = 1_000.0
    # 1) background traffic (also warms up the online anomaly model)
    for _ in range(n_background):
        t += rng.uniform(0.5, 3)
        cid = rng.choice(ids)
        kind = rng.choices(["card_payment", "card_declined", "ach_credit", "instant_transfer", "login"],
                           [55, 4, 8, 12, 21])[0]
        amt = {"card_payment": rng.lognormvariate(7, 0.6), "card_declined": rng.lognormvariate(7, 0.6),
               "ach_credit": rng.lognormvariate(9.5, 0.5), "instant_transfer": rng.lognormvariate(8, 0.6),
               "login": 0}[kind]
        yield _ev(cid, kind, amt, t, rng.choice(COUNTRIES), rng.choice(MERCHANTS))

    # 2) scripted scenarios, interleaved with a little background noise
    # Scenario A: risky transfer -> normal history, then big foreign transfer
    a = SCENARIO_CUSTOMERS["risky_transfer"]
    for _ in range(8):
        t += 2
        yield _ev(a, "card_payment", rng.uniform(900, 1500), t, "IN", "grocer")
    t += 5
    yield _ev(a, "wire_out", 450_000, t, "AE", "", "wire")

    # Scenario B: large deposit -> eligibility + propensity -> personalised offer
    b = SCENARIO_CUSTOMERS["large_deposit"]
    for _ in range(6):
        t += 2
        yield _ev(b, "card_payment", rng.uniform(1000, 2500), t, "IN", "dining")
    t += 5
    yield _ev(b, "ach_credit", 600_000, t, "IN", "", "ach")

    # Scenario C: repeated card declines -> assistance / agent script
    c = SCENARIO_CUSTOMERS["card_decline"]
    for _ in range(4):
        t += 2
        yield _ev(c, "card_payment", rng.uniform(800, 1800), t, "IN", "ecom")
    for _ in range(3):
        t += 4
        yield _ev(c, "card_declined", 25_000, t, "IN", "travel", "card")

    for _ in range(30):  # tail noise
        t += rng.uniform(0.5, 3)
        yield _ev(rng.choice(ids), "login", 0, t)


class SimulatedStream(pw.io.python.ConnectorSubject):
    """Pathway Custom Python Connector: replays events with a speed factor.
    speed<=0 means 'as fast as possible' (used in tests); every event is its own commit
    so the engine computes per-event decisions."""

    def __init__(self, events: Iterator[dict] | list[dict], speed: float = 20.0):
        super().__init__()
        self.events = list(events)
        self.speed = speed

    def run(self):
        prev = None
        for e in self.events:
            if self.speed > 0 and prev is not None:
                time.sleep(max(0.0, min(0.25, (e["ts"] - prev) / self.speed)))
            prev = e["ts"]
            self.next(**e, emit_wall=time.time())
            self.commit()
        self.close()


def read_stream(events=None, speed: float = 20.0) -> pw.Table:
    src = SimulatedStream(events if events is not None else generate(), speed)
    return pw.io.python.read(src, schema=RawEvent, autocommit_duration_ms=None)
