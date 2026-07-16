import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("CHAPPIE_MODEL", "claude-haiku-4-5")
PORT = int(os.environ.get("PORT", "8000"))
HOST = os.environ.get("HOST", "0.0.0.0")
MOCK_LLM = os.environ.get("MOCK_LLM", "0") == "1"

STATE_PATH = Path(os.environ.get("CHAPPIE_STATE_PATH", str(REPO_ROOT / "state.json")))
PERSIST_INTERVAL_S = float(os.environ.get("CHAPPIE_PERSIST_INTERVAL_S", "10"))
TICK_HZ = float(os.environ.get("CHAPPIE_TICK_HZ", "20"))
HISTORY_MAX_TURNS = 8

ADMIN_TOKEN = os.environ.get("CHAPPIE_ADMIN_TOKEN", "")
