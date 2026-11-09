"""ML signals.

* River HalfSpaceTrees  -> streaming anomaly score per event (online, learns as events arrive)
* LightGBM x3           -> churn, offer-propensity, inferred life-event (trained offline on SYNTHETIC data)

NOTE: the LightGBM models are trained on synthetic labels generated from a hidden
ground-truth function, so reported AUCs only prove the plumbing works - they are NOT
real-world performance. Swap `synth_dataset()` for real outcome data to use this in earnest.
"""
import math

import lightgbm as lgb
import numpy as np
from river import anomaly

from . import config

FEATURES = ["tenure_months", "n_events", "avg_amount", "decline_rate", "vel_cnt",
            "last_amount_ratio", "deposit_share", "transfer_share", "max_anomaly"]
TARGETS = ["churn", "offer", "life"]


# ---------------------------------------------------------------- online anomaly (River)
_hst = anomaly.HalfSpaceTrees(n_trees=15, height=6, window_size=60, seed=42)


def anomaly_score(etype: str, amount: float, country: str) -> float:
    """Score the event with the current model, then learn from it (test-then-train)."""
    x = {
        "amt": min(1.0, math.log1p(max(amount, 0.0)) / math.log1p(1_000_000)),
        "foreign": 0.0 if country == "IN" else 1.0,
        "transfer": 1.0 if etype == "TRANSFER_OUT" else 0.0,
        "decline": 1.0 if etype == "CARD_DECLINE" else 0.0,
        "deposit": 1.0 if etype == "DEPOSIT" else 0.0,
    }
    s = _hst.score_one(x)
    _hst.learn_one(x)
    return float(s)


# ---------------------------------------------------------------- synthetic training data
def _sig(z):
    return 1 / (1 + np.exp(-z))


def synth_dataset(n: int = 6000, seed: int = 0):
    rng = np.random.default_rng(seed)
    X = np.column_stack([
        rng.integers(1, 120, n),                      # tenure_months
        rng.integers(1, 80, n),                       # n_events
        rng.lognormal(7.2, 0.7, n),                   # avg_amount
        rng.beta(1.2, 12, n),                         # decline_rate
        rng.integers(0, 12, n),                       # vel_cnt
        rng.lognormal(0, 0.8, n),                     # last_amount_ratio
        rng.beta(2, 8, n),                            # deposit_share
        rng.beta(2, 8, n),                            # transfer_share
        rng.beta(1.5, 6, n),                          # max_anomaly
    ])
    ten, nev, avg, dec, vel, lar, dep, tr, anom = X.T
    y_churn = rng.random(n) < _sig(-1.2 + 6 * dec - 0.04 * nev - 0.12 * vel - 0.01 * ten + 1.5 * anom)
    y_offer = rng.random(n) < _sig(-2.0 + 4 * dep + 0.6 * np.log(lar + 1e-3) + 0.01 * ten - 2 * dec)
    y_life = rng.random(n) < _sig(-3.0 + 1.1 * np.log(lar + 1e-3) + 3 * dep + 2 * tr)
    return X, {"churn": y_churn, "offer": y_offer, "life": y_life}


def train_all(verbose: bool = True) -> dict:
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split
    config.MODEL_DIR.mkdir(exist_ok=True)
    X, ys = synth_dataset()
    report = {}
    for name in TARGETS:
        Xtr, Xte, ytr, yte = train_test_split(X, ys[name], test_size=0.25, random_state=1, stratify=ys[name])
        m = lgb.LGBMClassifier(n_estimators=120, learning_rate=0.06, num_leaves=15, verbose=-1)
        m.fit(Xtr, ytr)
        auc = roc_auc_score(yte, m.predict_proba(Xte)[:, 1])
        m.booster_.save_model(str(config.MODEL_DIR / f"{name}.txt"))
        report[name] = round(float(auc), 3)
    if verbose:
        print("synthetic-data AUC (plumbing check only):", report)
    return report


_boosters: dict[str, lgb.Booster] = {}


def predict(name: str, feats: list[float]) -> float:
    if name not in _boosters:
        path = config.MODEL_DIR / f"{name}.txt"
        if not path.exists():
            train_all(verbose=False)
        _boosters[name] = lgb.Booster(model_file=str(path))
    return float(_boosters[name].predict(np.asarray([feats], dtype=float))[0])


if __name__ == "__main__":
    train_all()
