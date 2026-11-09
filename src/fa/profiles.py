"""Static customer reference data (KYC, products, consent) – joined into the live 360."""
import csv
import random

from . import config
from .simulator import SCENARIO_CUSTOMERS, customer_ids

PROFILE_PATH = config.DATA_DIR / "customers.csv"


def build_profiles(n_customers: int = 30, seed: int = 11) -> None:
    rng = random.Random(seed)
    rows = []
    for cid in customer_ids(n_customers):
        rows.append(dict(customer_id=cid, segment=rng.choice(["mass", "affluent", "premium"]),
                         kyc_status=rng.choices(["verified", "pending"], [92, 8])[0],
                         tenure_months=rng.randint(2, 96), credit_ok=int(rng.random() > 0.1),
                         marketing_consent=int(rng.random() > 0.2)))
    for cid in SCENARIO_CUSTOMERS.values():
        rows.append(dict(customer_id=cid, segment="affluent", kyc_status="verified",
                         tenure_months=48, credit_ok=1, marketing_consent=1))
    config.DATA_DIR.mkdir(exist_ok=True)
    with open(PROFILE_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    build_profiles()
    print("wrote", PROFILE_PATH)
