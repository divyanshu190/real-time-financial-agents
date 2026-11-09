# Project status and evidence boundary

## Current state

The repository contains a non-empty prototype implementation alongside the architecture design. The presence of source files does not mean the system has been integrated with real financial data or validated for production.

| Capability | Current evidence in repository | Honest status |
|---|---|---|
| Architecture | `architecture.png`, `architecture.mmd`, this mapping | Designed |
| Event stream | `simulator.py` | Simulated |
| Event normalization | `schema.py`, `pipeline.py` | Prototype code |
| Customer 360 | `pipeline.py` | Prototype code |
| Online anomaly detection | River model in `ml.py` | Prototype; trained online on simulated events |
| Churn / offer / life-event models | Synthetic data generator and LightGBM training in `ml.py` | Synthetic-only |
| Eligibility / triggers | `decisioning.py` | Rule-based prototype |
| Next-best action | `decisioning.py` | Heuristic scoring |
| Agent and guardrails | `agent.py`, `personalize.py`, `guardrails.py` | Prototype |
| Gateway / audit | `gateway.py` | Prototype |
| Feedback-driven retraining | No complete outcome-label-retrain pipeline | Planned |
| Real-data evaluation | No real dataset or evaluation report | Not done |
| Production integrations | No live provider credentials/connectors | Not done |

## Validation performed while preparing this repository

- The ZIP archive was inspected and its source, tests, data, model artifacts, and documentation were reviewed.
- The test suite was attempted in the preparation environment.
- Test collection failed because the environment did not have the `pathway` Python package installed (`ModuleNotFoundError: pathway`).
- Therefore, **the test suite is not verified as passing**. Install dependencies in a compatible environment and rerun `make test`.

## What you can safely claim

You can say:
- You designed the end-to-end architecture.
- You built or assembled a prototype of the streaming and decisioning pipeline, if you can explain the source code and demonstrate it.
- You used simulated financial events to exercise the workflow.
- You explored River online anomaly scoring and LightGBM signal integration with synthetic labels.

Do not say:
- The models were trained on real banking data.
- The system detects fraud accurately in production.
- The system has production-grade real-time integrations.
- Feedback-based continuous learning is complete.
- The reported metrics prove business or model performance.

## Before publishing

1. Read and understand every module you plan to claim as your work.
2. Install dependencies and run tests locally.
3. Run the demo and inspect generated outputs.
4. Remove any outputs that you cannot reproduce.
5. Replace synthetic labels with a documented, legally usable dataset before making model-performance claims.
