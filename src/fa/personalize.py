"""Grounded personalisation. The LLM never decides *what* to do (the trigger engine + NBA do);
it only phrases a message from pipeline-provided facts. Default = deterministic templates (offline)."""
import json

from . import config

POLICY_DIR = config.DATA_DIR / "policies"


def policy_text(action: str) -> str:
    """Live policy lookup: re-read on every call so edited policy files take effect immediately."""
    p = POLICY_DIR / f"{action}.txt"
    return p.read_text().strip() if p.exists() else ""


def _latest(facts, n=3):
    return list(facts)[-n:]


def template_message(trigger: str, action: str, facts: list[tuple]) -> str:
    ts, eid, text = facts[-1]
    ref = f"[ref: {eid}]"
    if action == "EXTRA_VERIFICATION":
        return f"For your security we paused a transaction ({text}) and need one extra verification step. {ref}"
    if action == "ASSIST_CALL_SCRIPT":
        refs = " ".join(f"[ref: {f[1]}]" for f in _latest(facts, 3))
        return (f"Agent script: customer had repeated declined card attempts (latest: {text}). Confirm identity, "
                f"check card limits / travel flags, offer to reissue or raise the limit. {refs}")
    if action == "PREAPPROVED_LOAN_OFFER":
        return f"Thanks for your recent deposit ({text}). You may qualify for a pre-approved loan offer. {ref}"
    if action == "SAVINGS_OFFER":
        return f"Thanks for your recent deposit ({text}). Consider moving idle funds into a higher-yield savings plan. {ref}"
    if action == "RETENTION_OFFER":
        return f"We value you as a customer. Here is a special offer based on your recent activity ({text}). {ref}"
    return ""


def summary3(trigger: str, action: str, facts: list[tuple], reasons: list[str]) -> list[str]:
    return [f"Latest event: {facts[-1][2]} [ref: {facts[-1][1]}]",
            f"Why triggered: {trigger} ({'; '.join(reasons[:3])})",
            f"Next action: {action}"]


def llm_message(trigger: str, action: str, facts: list[tuple]) -> str | None:
    """Optional LLM phrasing grounded ONLY in supplied facts. Returns None on any failure
    (caller falls back to the template). Requires `pip install anthropic` + ANTHROPIC_API_KEY."""
    try:
        import anthropic
        prompt = (
            "Write a 1-2 sentence customer-facing banking message. Use ONLY these facts and cite the "
            "source id of any fact you use as [ref: <id>]. Do not invent numbers, offers or promises.\n"
            f"Action: {action}\nPolicy: {policy_text(action)}\nFacts: {json.dumps(_latest(facts))}")
        r = anthropic.Anthropic().messages.create(
            model=config.LLM_MODEL, max_tokens=200, messages=[{"role": "user", "content": prompt}])
        return r.content[0].text.strip()
    except Exception:
        return None


def build_message(trigger: str, action: str, facts: list[tuple]) -> tuple[str, str]:
    if config.LLM_PROVIDER == "anthropic":
        m = llm_message(trigger, action, facts)
        if m:
            return m, "llm"
    return template_message(trigger, action, facts), "template"
