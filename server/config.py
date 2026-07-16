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

# Voz (HANDOFF §7 fase 2): unica voz masculina pt-BR do Edge TTS e Antonio.
# rate/pitch aqui sao so um leve ajuste de base — o timbre "androide de
# cinema" de verdade vem do pos-processo ffmpeg em server/tts.py.
TTS_VOICE = os.environ.get("CHAPPIE_TTS_VOICE", "pt-BR-AntonioNeural")
TTS_RATE = os.environ.get("CHAPPIE_TTS_RATE", "-8%")
TTS_PITCH = os.environ.get("CHAPPIE_TTS_PITCH", "-4Hz")
