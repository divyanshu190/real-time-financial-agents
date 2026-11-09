"""Event-triggered agent: plans a short tool sequence per action, enforces tool permissions,
and records every tool call (inputs, outputs) in the trace. Tools are plain functions here;
mcp_server.py exposes the same read-only tools over the Model Context Protocol."""
import time
from dataclasses import dataclass, field

from .personalize import policy_text

PERMISSIONS = {   # role -> allowed tools (least privilege)
    "engagement_agent": {"lookup_facts", "get_policy"},
    "analyst": {"lookup_facts", "get_policy", "get_decision"},
}
PLAN = {
    "EXTRA_VERIFICATION": ["lookup_facts"],
    "ASSIST_CALL_SCRIPT": ["lookup_facts", "get_policy"],
    "PREAPPROVED_LOAN_OFFER": ["lookup_facts", "get_policy"],
    "SAVINGS_OFFER": ["lookup_facts", "get_policy"],
    "RETENTION_OFFER": ["lookup_facts", "get_policy"],
}


@dataclass
class Trace:
    steps: list = field(default_factory=list)

    def add(self, tool, args, result_preview, ok=True, ms=0.0):
        self.steps.append({"tool": tool, "args": args, "ok": ok, "ms": round(ms, 2),
                           "result": str(result_preview)[:160]})


def run_agent(action: str, customer_id: str, facts: list[tuple], role="engagement_agent",
              retries: int = 1) -> tuple[dict, Trace]:
    tools = {
        "lookup_facts": lambda: [f[2] for f in facts[-3:]],
        "get_policy": lambda: policy_text(action),
    }
    trace, ctx = Trace(), {}
    for tool in PLAN.get(action, []):
        if tool not in PERMISSIONS[role]:
            trace.add(tool, {"customer_id": customer_id}, "DENIED", ok=False)
            continue
        for attempt in range(retries + 1):          # simple retry/timeout-safe wrapper
            t0 = time.perf_counter()
            try:
                ctx[tool] = tools[tool]()
                trace.add(tool, {"customer_id": customer_id}, ctx[tool], ms=(time.perf_counter() - t0) * 1e3)
                break
            except Exception as e:                    # noqa: BLE001
                trace.add(tool, {"customer_id": customer_id}, f"ERROR {e}", ok=False)
    return ctx, trace
