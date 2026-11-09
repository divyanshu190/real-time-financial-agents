"""Optional MCP server exposing read-only tools over the pipeline's output (actions.jsonl).
Run:  python -m fa.mcp_server     (stdio transport; needs `pip install mcp`)
Any MCP client / agent can then call get_decision, list_actions, get_metrics."""
import json

from . import config


def _records():
    p = config.OUT_DIR / "actions.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def get_decision(customer_id: str) -> dict:
    """Latest decision (trigger, action, reasons, signals) for a customer."""
    rs = [r for r in _records() if r["customer_id"] == customer_id]
    return rs[-1] if rs else {"error": "unknown customer or no decisions yet"}


def list_actions(limit: int = 20) -> list:
    """Most recent actions that were sent (or suppressed by the kill switch)."""
    return [r for r in _records() if r["status"] != "NO_ACTION"][-limit:]


def get_metrics() -> dict:
    p = config.OUT_DIR / "metrics.json"
    return json.loads(p.read_text()) if p.exists() else {}


if __name__ == "__main__":
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("customer360")
    for fn in (get_decision, list_actions, get_metrics):
        mcp.tool()(fn)
    mcp.run()
