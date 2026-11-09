"""Pathway dataflow: raw events -> standardised events -> live Customer 360 -> signals -> decisions.

Everything here is incremental: each new event updates only the affected customer rows.
"""
import pathway as pw

from . import config
from .decisioning import decide
from .ml import anomaly_score, predict
from .schema import RawEvent, canonical_type

TXN = ("CARD_PAYMENT", "DEPOSIT", "TRANSFER_OUT")


class ProfileSchema(pw.Schema):
    customer_id: str
    segment: str
    kyc_status: str
    tenure_months: int
    credit_ok: int
    marketing_consent: int


def read_profiles(path=None) -> pw.Table:
    from .profiles import PROFILE_PATH, build_profiles
    p = path or PROFILE_PATH
    if not p.exists():
        build_profiles()
    # static here; use mode="streaming" to hot-reload KYC / consent changes
    return pw.io.csv.read(str(p), schema=ProfileSchema, mode="static")


# ------------------------------------------------------------------ stage 1: standardise
def standardise(raw: pw.Table) -> pw.Table:
    E = raw.select(
        raw.event_id, raw.customer_id, raw.amount, raw.country, raw.merchant, raw.channel,
        raw.ts, raw.emit_wall,
        etype=pw.apply(canonical_type, raw.event_type),
    )
    # online anomaly score (River HalfSpaceTrees): append-only table => each event scored once
    return E.with_columns(anomaly=pw.apply(anomaly_score, E.etype, E.amount, E.country))


# ------------------------------------------------------------------ stage 2: live Customer 360
def customer_360(E: pw.Table) -> pw.Table:
    is_txn = (E.etype == "CARD_PAYMENT") | (E.etype == "DEPOSIT") | (E.etype == "TRANSFER_OUT")
    S = E.groupby(E.customer_id).reduce(
        customer_id=E.customer_id,
        n_events=pw.reducers.count(),
        n_txn=pw.reducers.sum(pw.if_else(is_txn, 1, 0)),
        txn_sum=pw.reducers.sum(pw.if_else(is_txn, E.amount, 0.0)),
        n_decl=pw.reducers.sum(pw.if_else(E.etype == "CARD_DECLINE", 1, 0)),
        n_dep=pw.reducers.sum(pw.if_else(E.etype == "DEPOSIT", 1, 0)),
        n_tr=pw.reducers.sum(pw.if_else(E.etype == "TRANSFER_OUT", 1, 0)),
        max_anomaly=pw.reducers.max(E.anomaly),
        last_ptr=pw.reducers.argmax(E.ts),
    )
    S = S.select(
        *pw.this.without(pw.this.last_ptr),
        last_event_id=E.ix(S.last_ptr).event_id,
        last_type=E.ix(S.last_ptr).etype,
        last_amount=E.ix(S.last_ptr).amount,
        last_country=E.ix(S.last_ptr).country,
        last_anomaly=E.ix(S.last_ptr).anomaly,
        last_ts=E.ix(S.last_ptr).ts,
        emit_wall=E.ix(S.last_ptr).emit_wall,
    )
    # stateful sliding windows -> velocity features, latest window per customer
    W = E.windowby(
        E.ts,
        window=pw.temporal.sliding(hop=config.WINDOW_HOP_SEC, duration=config.WINDOW_SEC),
        instance=E.customer_id,
    ).reduce(
        customer_id=pw.this._pw_instance,
        wend=pw.this._pw_window_end,
        w_cnt=pw.reducers.count(),
        w_decl=pw.reducers.sum(pw.if_else(pw.this.etype == "CARD_DECLINE", 1, 0)),
    )
    WL = W.groupby(W.customer_id).reduce(customer_id=W.customer_id, wptr=pw.reducers.argmax(W.wend))
    WL = WL.select(WL.customer_id, vel_cnt=W.ix(WL.wptr).w_cnt, win_declines=W.ix(WL.wptr).w_decl)
    return S.join(WL, S.customer_id == WL.customer_id).select(*S, WL.vel_cnt, WL.win_declines)


def minute_metrics(E: pw.Table) -> pw.Table:
    """'Always up-to-date metrics': per-minute volume / declines (tumbling event-time window)."""
    return E.windowby(E.ts, window=pw.temporal.tumbling(duration=60)).reduce(
        window_start=pw.this._pw_window_start,
        events=pw.reducers.count(),
        volume=pw.reducers.sum(pw.this.amount),
        declines=pw.reducers.sum(pw.if_else(pw.this.etype == "CARD_DECLINE", 1, 0)),
        max_anomaly=pw.reducers.max(pw.this.anomaly),
    )


# ------------------------------------------------------------------ stage 3: signals + decisions
def _prior_avg(n_txn, txn_sum, last_type, last_amount):
    if last_type in TXN:
        n, s = n_txn - 1, txn_sum - last_amount
    else:
        n, s = n_txn, txn_sum
    return s / n if n > 0 else 1000.0


def _features(tenure, n_events, avg, n_decl, vel, last_amt, n_dep, n_tr, max_anom):
    n = max(n_events, 1)
    return [float(tenure), float(n_events), float(avg), n_decl / n, float(vel),
            last_amt / max(avg, 1.0), n_dep / n, n_tr / n, float(max_anom)]


def _signal(name):
    def f(*args):
        return predict(name, _features(*args))
    return f


def decisions(S: pw.Table, profiles: pw.Table, facts: pw.Table) -> pw.Table:
    J = S.join_left(profiles, S.customer_id == profiles.customer_id).select(
        *S,
        segment=pw.coalesce(profiles.segment, "unknown"),
        kyc_status=pw.coalesce(profiles.kyc_status, "pending"),
        tenure_months=pw.coalesce(profiles.tenure_months, 0),
        credit_ok=pw.coalesce(profiles.credit_ok, 0),
        marketing_consent=pw.coalesce(profiles.marketing_consent, 0),
    )
    J = J.with_columns(
        avg_amount=pw.apply(_prior_avg, J.n_txn, J.txn_sum, J.last_type, J.last_amount),
        n_hist=pw.apply(lambda n, t: n - 1 if t in TXN else n, J.n_txn, J.last_type),
    )
    args = (J.tenure_months, J.n_events, J.avg_amount, J.n_decl, J.vel_cnt, J.last_amount,
            J.n_dep, J.n_tr, J.max_anomaly)
    J = J.with_columns(
        p_churn=pw.apply(_signal("churn"), *args),
        p_offer=pw.apply(_signal("offer"), *args),
        p_life=pw.apply(_signal("life"), *args),
    )
    keys = ["customer_id", "kyc_status", "credit_ok", "marketing_consent", "tenure_months", "last_type",
            "last_amount", "last_country", "last_anomaly", "avg_amount", "n_hist", "win_declines",
            "p_churn", "p_offer", "p_life"]
    D = J.with_columns(decision=pw.apply_with_type(
        lambda *v: decide(dict(zip(keys, v))), str, *[J[k] for k in keys]))
    return D.join_left(facts, D.customer_id == facts.customer_id).select(*D, facts=facts.facts)


# ------------------------------------------------------------------ live fact index
def live_facts(E: pw.Table) -> pw.Table:
    """Per-customer index of source-linked facts, updated incrementally as events arrive.
    (Swap for pathway.xpacks.llm DocumentStore + embedder for semantic retrieval over documents.)"""
    txt = pw.apply(lambda t, a, c, m, ch: f"{t} of INR {a:,.0f} via {ch} ({c}{', ' + m if m else ''})",
                   E.etype, E.amount, E.country, E.merchant, E.channel)
    return E.groupby(E.customer_id).reduce(
        customer_id=E.customer_id,
        facts=pw.reducers.sorted_tuple(pw.make_tuple(E.ts, E.event_id, txt)),
    )


def build(raw: pw.Table, profiles: pw.Table):
    E = standardise(raw)
    S = customer_360(E)
    D = decisions(S, profiles, live_facts(E))
    return E, D, minute_metrics(E)
