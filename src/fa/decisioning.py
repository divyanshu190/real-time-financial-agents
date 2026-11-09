"""Deterministic offer eligibility, real-time trigger engine and next-best-action scoring.
Pure functions -> trivially unit-testable and explainable (every decision returns reason codes)."""
import json

from . import config

# action -> (business value if accepted, friction cost)
ACTION_VALUE = {
    "RETENTION_OFFER": (6.0, 0.5),
    "PREAPPROVED_LOAN_OFFER": (9.0, 1.0),
    "SAVINGS_OFFER": (4.0, 0.3),
    "ASSIST_CALL_SCRIPT": (3.0, 0.8),
    "EXTRA_VERIFICATION": (8.0, 1.5),
}


def eligibility(profile: dict) -> tuple[bool, list[str]]:
    reasons = []
    if profile["kyc_status"] != "verified":
        reasons.append("KYC_NOT_VERIFIED")
    if not profile["credit_ok"]:
        reasons.append("CREDIT_FLAG")
    if not profile["marketing_consent"]:
        reasons.append("NO_MARKETING_CONSENT")
    if profile["tenure_months"] < 3:
        reasons.append("TENURE_TOO_SHORT")
    return (len(reasons) == 0, reasons or ["ELIGIBLE"])


def trigger(s: dict) -> tuple[str, list[str]]:
    """s = live Customer-360 row. First matching trigger wins (authorization-sensitive first)."""
    et, amt, avg = s["last_type"], s["last_amount"], max(s["avg_amount"], 1.0)
    foreign = s["last_country"] != "IN"
    ratio = amt / avg
    has_history = s["n_hist"] >= 3                  # ratio rules need a baseline
    if et == "TRANSFER_OUT" and has_history and (
        (ratio >= 4 and s["last_anomaly"] >= config.RISKY_ANOMALY)
        or (ratio >= config.RISKY_AMOUNT_RATIO and foreign)
        or ratio >= 10
    ):
        return "RISKY_TRANSFER", [f"amount={amt:.0f}", f"avg={avg:.0f}", f"foreign={foreign}",
                                  f"anomaly={s['last_anomaly']:.2f}"]
    if s["win_declines"] >= config.DECLINE_STREAK:
        return "CARD_DECLINE_STREAK", [f"declines_in_window={s['win_declines']}"]
    if et == "DEPOSIT" and amt >= config.LARGE_DEPOSIT_MIN and (not has_history or ratio >= config.LARGE_DEPOSIT_RATIO):
        return "LARGE_DEPOSIT", [f"amount={amt:.0f}", f"avg={avg:.0f}"]
    if s["p_churn"] >= config.CHURN_P:
        return "CHURN_RISK", [f"p_churn={s['p_churn']:.2f}"]
    return "NONE", []


def next_best_action(trig: str, s: dict, eligible: bool) -> tuple[str, float, list[str]]:
    """Expected-utility ranking over candidate actions allowed for this trigger.
    (Hook: replace `p` with a LightGBM ranker once real outcome data exists.)"""
    if trig == "NONE":
        return "NO_ACTION", 0.0, []
    candidates: dict[str, float] = {}
    if trig == "RISKY_TRANSFER":
        candidates["EXTRA_VERIFICATION"] = max(s["last_anomaly"], 0.7)
    elif trig == "CARD_DECLINE_STREAK":
        candidates["ASSIST_CALL_SCRIPT"] = 0.9
    elif trig == "LARGE_DEPOSIT" and eligible:
        candidates["PREAPPROVED_LOAN_OFFER"] = s["p_offer"] * 0.5
        candidates["SAVINGS_OFFER"] = s["p_offer"]
    elif trig == "CHURN_RISK" and eligible:
        candidates["RETENTION_OFFER"] = s["p_churn"] * 0.6
    if not candidates:
        return "NO_ACTION", 0.0, ["NOT_ELIGIBLE_FOR_OFFERS"] if not eligible else []
    scored = {a: p * ACTION_VALUE[a][0] - ACTION_VALUE[a][1] for a, p in candidates.items()}
    best = max(scored, key=scored.get)
    return best, round(scored[best], 3), [f"{a}:{v:.2f}" for a, v in sorted(scored.items())]


def decide(row: dict) -> str:
    """Single entry point used inside the Pathway dataflow. Returns JSON (explainable)."""
    ok, ereasons = eligibility(row)
    trig, treasons = trigger(row)
    action, score, scores = next_best_action(trig, row, ok)
    return json.dumps({"trigger": trig, "action": action, "score": score,
                       "eligible": ok, "reasons": treasons + ereasons + scores})
