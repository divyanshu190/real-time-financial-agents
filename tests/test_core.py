import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fa import decisioning, guardrails          # noqa: E402
from fa.schema import canonical_type             # noqa: E402


def row(**kw):
    base = dict(last_type="CARD_PAYMENT", last_amount=1000, last_country="IN", last_anomaly=0.1,
                avg_amount=1000, n_hist=10, win_declines=0, p_churn=0.1, p_offer=0.5, p_life=0.1,
                kyc_status="verified", credit_ok=1, marketing_consent=1, tenure_months=24)
    base.update(kw)
    return base


def test_canonical_types():
    assert canonical_type("ACH_credit") == "DEPOSIT" and canonical_type("weird") == "OTHER"


def test_risky_transfer_needs_baseline():
    assert decisioning.trigger(row(last_type="TRANSFER_OUT", last_amount=450_000, last_country="AE"))[0] == "RISKY_TRANSFER"
    assert decisioning.trigger(row(last_type="TRANSFER_OUT", last_amount=450_000, n_hist=1))[0] == "NONE"


def test_decline_streak_and_deposit():
    assert decisioning.trigger(row(win_declines=3))[0] == "CARD_DECLINE_STREAK"
    assert decisioning.trigger(row(last_type="DEPOSIT", last_amount=600_000))[0] == "LARGE_DEPOSIT"


def test_ineligible_customer_gets_no_offer():
    d = json.loads(decisioning.decide(row(last_type="DEPOSIT", last_amount=600_000, kyc_status="pending")))
    assert d["trigger"] == "LARGE_DEPOSIT" and d["action"] == "NO_ACTION" and not d["eligible"]


def test_guardrails():
    facts = [(1.0, "e-abc", "DEPOSIT of INR 600,000 via ach (IN)")]
    ok, _ = guardrails.check("Thanks for your deposit of 600,000. [ref: e-abc]", "LARGE_DEPOSIT", "SAVINGS_OFFER", facts)
    assert ok
    assert not guardrails.check("You got 999,999 INR [ref: e-abc]", "LARGE_DEPOSIT", "SAVINGS_OFFER", facts)[0]
    assert not guardrails.check("No citation here", "LARGE_DEPOSIT", "SAVINGS_OFFER", facts)[0]
    assert not guardrails.check("x [ref: e-abc]", "LARGE_DEPOSIT", "EXTRA_VERIFICATION", facts)[0]
    assert "REDACTED" in guardrails.redact("call 9876543210 or a@b.com [ref: e-1234567890]")
    assert "[ref: e-1234567890]" in guardrails.redact("call 9876543210 [ref: e-1234567890]")
