"""Response guardrails: every customer-facing message must pass ALL checks or a safe fallback is sent."""
import re

ALLOWED_ACTIONS = {
    "RISKY_TRANSFER": {"EXTRA_VERIFICATION"},
    "CARD_DECLINE_STREAK": {"ASSIST_CALL_SCRIPT"},
    "LARGE_DEPOSIT": {"PREAPPROVED_LOAN_OFFER", "SAVINGS_OFFER"},
    "CHURN_RISK": {"RETENTION_OFFER"},
}
_PII = [
    (re.compile(r"\b\d{12,19}\b"), "[REDACTED_NUMBER]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[REDACTED_EMAIL]"),
    (re.compile(r"(?<!\w)\+?\d[\d -]{8,}\d"), "[REDACTED_PHONE]"),
]
FALLBACK = ("We noticed recent activity on your account. A specialist will review it and contact you "
            "through your registered channel if anything is needed.")


_REF = re.compile(r"(\[ref: [^\]]*\])")


def redact(text: str) -> str:
    """Mask PII everywhere except inside [ref: <id>] citations (ids are opaque, not PII)."""
    parts = _REF.split(text)
    for i in range(0, len(parts), 2):
        for rx, rep in _PII:
            parts[i] = rx.sub(rep, parts[i])
    return "".join(parts)


def check(message: str, trigger: str, action: str, facts: list[tuple]) -> tuple[bool, list[str]]:
    """facts: [(ts, event_id, text)]. Returns (ok, failed_checks)."""
    failed = []
    blob = " ".join(f[2] for f in facts)
    body = re.sub(r"\[ref: [^\]]*\]", "", message)          # citations are checked separately
    if action not in ALLOWED_ACTIONS.get(trigger, set()):
        failed.append("ACTION_NOT_PERMITTED_FOR_TRIGGER")
    if not any(f"[ref: {f[1]}]" in message for f in facts):
        failed.append("MISSING_SOURCE_CITATION")
    for num in re.findall(r"\d[\d,]{2,}", body):
        if num not in blob and not re.fullmatch(r"\d{4}", num):   # numbers must exist in facts
            failed.append(f"UNGROUNDED_NUMBER:{num}")
    if redact(message) != message:
        failed.append("PII_IN_OUTPUT")
    return (not failed, failed)
