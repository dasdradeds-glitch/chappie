#!/data/data/com.termux/files/usr/bin/bash
# Atualiza codigo + deps e reinicia o servico. Uso: bash deploy/update.sh
# Contraparte "no terminal" do POST /admin/update (que so faz pull de codigo).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Atualizando Chappie..."
git pull --ff-only

if command -v pkg >/dev/null 2>&1 && ! command -v ffmpeg >/dev/null 2>&1; then
  pkg install -y ffmpeg
fi

VENV_PY=".venv/bin/pip"
[ -f "$VENV_PY" ] || VENV_PY=".venv/Scripts/pip"
"$VENV_PY" install --quiet -r requirements.txt

if command -v sv >/dev/null 2>&1 && [ -d "${PREFIX:-/nonexistent}/var/service/chappie" ]; then
  sv restart chappie
  echo "Servico reiniciado (runit)."
else
  echo "termux-services nao encontrado — se estiver rodando via dev/run_local.sh, reinicie manualmente (Ctrl+C e rode de novo)."
fi
