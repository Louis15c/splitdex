#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_ROOT/backend/.venv"
HOST="0.0.0.0"
PORT="8000"

if [ ! -d "$VENV_DIR" ]; then
  echo "Création de l'environnement virtuel..."
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

pip install --quiet --upgrade pip
pip install --quiet -r "$PROJECT_ROOT/backend/requirements.txt"

# Adresse IP locale — détection multiplateforme (macOS n'a pas `hostname -I`).
if command -v ipconfig >/dev/null 2>&1; then
  LOCAL_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"  # macOS
else
  LOCAL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"                                          # Linux
fi

echo ""
echo "Splitdex démarre sur http://$HOST:$PORT"
echo "Depuis un autre appareil du LAN, utilisez l'adresse IP de cette machine (voir README) :"
echo "  http://${LOCAL_IP:-<adresse-ip-locale>}:$PORT"
echo ""

cd "$PROJECT_ROOT/backend"
exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
