#!/data/data/com.termux/files/usr/bin/bash
# Chappie Companion — setup completo no Termux, em UM comando (HANDOFF v2 §4).
# Idempotente: rodar de novo so atualiza o que mudou, nao quebra nada.
#
# Uso normal (no Termux, apos instalar Termux + Termux:Boot pelo F-Droid):
#   bash <(curl -sL https://raw.githubusercontent.com/dasdradeds-glitch/chappie/main/deploy/bootstrap.sh)
#
# --dry-android : pula passos especificos de Android (pkg/termux-*), pra
#                 validar o resto do script num container Linux qualquer.
set -euo pipefail

REPO_URL="https://github.com/dasdradeds-glitch/chappie.git"
INSTALL_DIR="${CHAPPIE_INSTALL_DIR:-$HOME/chappie}"
PORT="${PORT:-8000}"
DRY_ANDROID=0

for arg in "$@"; do
  case "$arg" in
    --dry-android) DRY_ANDROID=1 ;;
  esac
done

log() { printf '\n\033[1;36m==>\033[0m %s\n' "$1"; }

log "1/7 Pacotes do sistema"
if [ "$DRY_ANDROID" = "1" ]; then
  echo "  (--dry-android: pulando pkg install)"
else
  pkg update -y
  pkg install -y python git termux-services termux-api
fi

log "2/7 Clonando/atualizando o repo em $INSTALL_DIR"
if [ -d "$INSTALL_DIR/.git" ]; then
  git -C "$INSTALL_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

log "3/7 Ambiente Python (venv + dependencias)"
if [ ! -d .venv ]; then
  python -m venv .venv
fi
VENV_PY=".venv/bin/python"
[ -f "$VENV_PY" ] || VENV_PY=".venv/Scripts/python.exe"  # so acontece fora do Termux (dry-run em dev)
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet -r requirements.txt

log "4/7 API key da Anthropic"
ENV_FILE="$INSTALL_DIR/.env"
if [ -f "$ENV_FILE" ] && grep -q '^ANTHROPIC_API_KEY=' "$ENV_FILE" 2>/dev/null; then
  echo "  .env ja tem ANTHROPIC_API_KEY — mantendo (apague o arquivo pra trocar)."
elif [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  printf 'ANTHROPIC_API_KEY=%s\nPORT=%s\n' "$ANTHROPIC_API_KEY" "$PORT" > "$ENV_FILE"
  echo "  Gravado em $ENV_FILE (via variavel de ambiente ANTHROPIC_API_KEY)."
elif [ -t 0 ]; then
  read -rp "  Cola a ANTHROPIC_API_KEY (sk-ant-...): " API_KEY
  printf 'ANTHROPIC_API_KEY=%s\nPORT=%s\n' "$API_KEY" "$PORT" > "$ENV_FILE"
  echo "  Gravado em $ENV_FILE"
else
  echo "  ERRO: sem terminal interativo pra pedir a API key." >&2
  echo "  Defina ANTHROPIC_API_KEY e rode de novo, ou crie $ENV_FILE na mao." >&2
  exit 1
fi
chmod 600 "$ENV_FILE"

log "5/7 Servico runit (autostart)"
if [ "$DRY_ANDROID" = "1" ]; then
  echo "  (--dry-android: pulando termux-services)"
else
  SERVICE_DIR="$PREFIX/var/service/chappie"
  mkdir -p "$SERVICE_DIR/log"
  cp "$INSTALL_DIR/deploy/chappie.service" "$SERVICE_DIR/run"
  chmod +x "$SERVICE_DIR/run"
  cat > "$SERVICE_DIR/log/run" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
exec logger -t chappie
EOF
  chmod +x "$SERVICE_DIR/log/run"
  sv-enable chappie 2>/dev/null || true
  sv restart chappie 2>/dev/null || sv start chappie 2>/dev/null || true
fi

log "6/7 Wake lock + bateria"
if [ "$DRY_ANDROID" = "1" ]; then
  echo "  (--dry-android: pulando termux-wake-lock)"
else
  termux-wake-lock || true
  echo "  IMPORTANTE (manual, o Android nao deixa automatizar isso):"
  echo "  Configuracoes > Bateria/Apps > Termux > Bateria > 'Sem restricoes'"
  echo "  (e depois o mesmo pro Chrome, depois que voce abrir o app)."
fi

log "7/7 Pronto"
URL="http://127.0.0.1:${PORT}"
echo "  Chappie no ar em: $URL"
echo ""
echo "  Proximo passo: abra essa URL no Chrome do celular, toque em"
echo "  'Adicionar a tela inicial', abra pelo icone, toque no microfone"
echo "  e permita o acesso quando o Android perguntar."
echo ""
if command -v qrencode >/dev/null 2>&1; then
  qrencode -t ANSIUTF8 "$URL"
else
  echo "  (opcional: 'pkg install qrencode' pra ver um QR code aqui)"
fi
