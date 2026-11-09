# Roadmap from architecture prototype to validated system

## Phase 1 — Reproducible prototype
- [ ] Create a clean Python 3.10–3.12 environment.
- [ ] Install pinned dependencies and verify Pathway API compatibility.
- [ ] Run unit and end-to-end tests.
- [ ] Run the simulator and save a reproducible demo transcript.
- [ ] Document expected outputs and known failure modes.

## Phase 2 — Data contracts and realistic evaluation
- [ ] Define event schemas, event-time semantics, late-arriving events, deduplication, and replay behavior.
- [ ] Obtain an authorized, de-identified dataset with provenance and permitted use.
- [ ] Define each prediction target, observation window, and prediction horizon.
- [ ] Build temporal/customer-level train-validation-test splits.
- [ ] Compare models against transparent baselines.
- [ ] Evaluate AUC/PR-AUC as appropriate, calibration, false-positive rates, subgroup performance, and drift.

## Phase 3 — Decision safety
- [ ] Define action-specific policy and consent checks.
- [ ] Add human approval for consequential or ambiguous actions.
- [ ] Add robust idempotency, retries, dead-letter handling, and durable audit storage.
- [ ] Threat-model prompt injection, tool misuse, data exfiltration, and replay attacks.
- [ ] Test guardrails adversarially; do not treat regex checks as compliance controls.

## Phase 4 — Production engineering
- [ ] Replace simulator with authenticated provider connectors.
- [ ] Persist customer state and online model state.
- [ ] Add model registry, versioning, rollback, and monitoring.
- [ ] Add observability for event lag, decision latency, failures, and action outcomes.
- [ ] Conduct privacy, security, regulatory, and model-risk reviews.

## Phase 5 — Feedback learning
- [ ] Capture outcomes with explicit definitions and timestamps.
- [ ] Link outcomes to decisions and model versions.
- [ ] Establish delayed-label handling and leakage-safe retraining.
- [ ] Run offline evaluation and approval before deployment.
- [ ] Monitor post-deployment performance and retain rollback capability.
