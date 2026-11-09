# Model card: prototype ML signals

## Intended use

Exercise the data and inference interfaces in a simulated financial-event pipeline. These models are not approved for customer-facing, credit, fraud, AML, or transaction authorization decisions.

## Models in the prototype

| Signal | Method | Training / update approach |
|---|---|---|
| Anomaly score | River HalfSpaceTrees | Online test-then-train updates over incoming simulated events |
| Churn risk | LightGBM binary classifier | Offline training on generated synthetic labels |
| Offer propensity | LightGBM binary classifier | Offline training on generated synthetic labels |
| Inferred life event | LightGBM binary classifier | Offline training on generated synthetic labels |

## Data

`src/fa/ml.py::synth_dataset` generates random feature vectors and labels from hand-written synthetic probability functions. The target labels are not derived from observed customer outcomes. No real customer records are included.

## Metrics

Any AUC produced by `train_all` measures how well a model learns the synthetic label-generating function on a held-out split. It does not estimate real-world predictive performance, calibration, fairness, or business lift.

## Limitations and risks

- Synthetic distributions may be unlike actual financial behavior.
- Labels encode the assumptions of the synthetic generator.
- No fairness, subgroup, calibration, drift, or stability evaluation is included.
- Online anomaly scores depend on stream order and in-memory model state.
- No model registry, durable state, approval workflow, or rollback process is implemented.

## Requirements before real use

Use a legally authorized dataset with documented provenance, define target labels and prediction horizons, prevent temporal leakage, create customer/time-based splits, compare against simple baselines, assess calibration and subgroup performance, monitor drift, and obtain model-risk, security, privacy, legal, and compliance review.
