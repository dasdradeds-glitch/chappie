#!/usr/bin/env bash
# Sobe o Chappie localmente pra dev, sem custo/rede: MOCK_LLM=1.
# Uso: bash dev/run_local.sh [porta]
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "Criando venv..."
  python -m venv .venv
fi

VENV_PY=".venv/Scripts/python"
[ -f "$VENV_PY" ] || VENV_PY=".venv/bin/python"

"$VENV_PY" -m pip install --quiet -r requirements.txt

export MOCK_LLM=1
export PORT="${1:-8000}"

echo "Chappie (MOCK_LLM=1) em http://127.0.0.1:${PORT}"
echo "Ctrl+C pra parar. Sem ANTHROPIC_API_KEY necessaria neste modo."
exec "$VENV_PY" -m uvicorn server.main:app --host 127.0.0.1 --port "$PORT"
