"""All tunables in one place; override with environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
MODEL_DIR = ROOT / "models"
OUT_DIR = Path(os.getenv("FA_OUT_DIR", ROOT / "out"))

# Feature windows (event-time seconds)
WINDOW_SEC = 300
WINDOW_HOP_SEC = 60

# Trigger thresholds
LARGE_DEPOSIT_MIN = float(os.getenv("LARGE_DEPOSIT_MIN", 100_000))
LARGE_DEPOSIT_RATIO = 5.0           # deposit >= 5x customer's average amount
RISKY_AMOUNT_RATIO = 4.0            # transfer >= 4x average amount
RISKY_ANOMALY = 0.80                # River HalfSpaceTrees score
DECLINE_STREAK = 3                  # declines inside one window
CHURN_P = 0.65

# Guardrails / ops
KILL_SWITCH_FILE = Path(os.getenv("KILL_SWITCH_FILE", ROOT / "KILL_SWITCH"))
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "template")     # template | anthropic
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5-5")
