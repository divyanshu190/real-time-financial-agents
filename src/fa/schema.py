import pathway as pw


class RawEvent(pw.Schema):
    """Raw event as emitted by any source (card, ACH, wire, ledger, app, support...)."""
    event_id: str
    customer_id: str
    event_type: str
    channel: str
    amount: float
    country: str
    merchant: str
    ts: float          # event time (seconds)
    emit_wall: float   # wall-clock when the event entered the system (latency KPI)


CANONICAL = {
    "card_payment": "CARD_PAYMENT", "card_declined": "CARD_DECLINE",
    "ach_credit": "DEPOSIT", "wire_in": "DEPOSIT", "deposit": "DEPOSIT",
    "wire_out": "TRANSFER_OUT", "instant_transfer": "TRANSFER_OUT", "ach_debit": "TRANSFER_OUT",
    "login": "APP_EVENT", "support_ticket": "SUPPORT",
}


def canonical_type(raw: str) -> str:
    return CANONICAL.get(raw.strip().lower(), "OTHER")
