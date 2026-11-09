# Architecture and component mapping

This document maps the supplied architecture diagram to the prototype source. The diagram is a system design; it should not be interpreted as proof that every production capability is complete.

## 1. Live data and streaming

**Diagram:** Live Inputs → Event Standardization → Pathway Streaming Engine

**Prototype files:**
- `src/fa/schema.py`: raw-event schema and canonical event types.
- `src/fa/simulator.py`: generates and replays synthetic events through a Pathway connector.
- `src/fa/pipeline.py::standardise`: normalizes event types and attaches anomaly scores.

**Not connected:** Real card, ACH, wire, ledger, brokerage, loan, KYC, CRM, or social-data providers. Production connectors, consent enforcement, schema contracts, and access controls must be added.

## 2. Live Customer 360 and incremental features

**Diagram:** keyed customer state → incremental feature engine

**Prototype files:**
- `src/fa/pipeline.py::customer_360`: per-customer aggregates and event-time sliding-window features.
- `src/fa/pipeline.py::decisions`: joins customer aggregates with profile attributes and computes model inputs.
- `src/fa/profiles.py`: creates demo customer profiles.

The current state is derived from the simulated event stream and local profile CSV. It is not a verified customer master record.

## 3. ML signals

**Diagram:** River HalfSpaceTrees anomaly score; LightGBM churn, offer propensity, and inferred life-event signals.

**Prototype file:** `src/fa/ml.py`

- River HalfSpaceTrees scores and learns from each simulated event.
- Three LightGBM classifiers are trained using generated synthetic labels.
- The models are useful for testing feature flow and model-serving integration, not for predicting real customer behavior.

See [`MODEL_CARD.md`](MODEL_CARD.md).

## 4. Triggers and decisioning

**Diagram:** deterministic eligibility + real-time trigger engine + next-best action.

**Prototype files:**
- `src/fa/decisioning.py`: trigger conditions, eligibility, reason codes, and action ranking.
- `src/fa/pipeline.py::decisions`: applies signal outputs to customer state.

The trigger/eligibility layer is designed to remain deterministic and auditable. The current next-best-action ranking is heuristic; it is not trained from observed customer outcomes.

## 5. Live facts, agent, and LLM

**Diagram:** live fact index → event-triggered agent → personalization → response guardrails.

**Prototype files:**
- `src/fa/pipeline.py::live_facts`: source-linked event facts keyed by customer.
- `src/fa/agent.py`: agent orchestration and tool/context handling.
- `src/fa/personalize.py`: template-based response and optional LLM phrasing.
- `src/fa/guardrails.py`: checks grounding, allowed actions, and PII patterns.

The current fact index is a structured keyed index, not a vector database or semantic document retrieval system. The LLM is a wording layer and must not be treated as the authority for eligibility, fraud, credit, or transaction authorization.

## 6. Action and evaluation

**Diagram:** action gateway → event/decision/action timestamps → feedback and continuous learning.

**Prototype files:**
- `src/fa/gateway.py`: action idempotency, output records, and kill-switch behavior.
- `src/fa/run.py`: starts the demo pipeline and output subscriptions.
- `out/`: generated runtime artifacts.

The feedback/retraining loop is not implemented end-to-end. The current repository does not establish production latency, availability, security, or business outcomes.

## 7. Demo scenarios

**Prototype file:** `src/fa/simulator.py`

- `C9001`: risky foreign transfer pattern.
- `C9002`: large deposit pattern.
- `C9003`: repeated card declines.

These IDs and events are synthetic fixtures. They must not be described as real customers or real fraud cases.

## Data flow in one line

`RawEvent → canonical event → online anomaly score → Customer 360 + window features → model probabilities → deterministic trigger / eligibility → heuristic NBA → source-linked facts → grounded message → guardrail → action gateway + audit record`
