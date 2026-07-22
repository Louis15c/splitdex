#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_ROOT/backend/.venv"
HOST="0.0.0.0"
PORT="8000"

# Sélection d'un interpréteur Python compatible.
# PyTorch, numpy & co. ne publient leurs binaires (« wheels ») que pour des
# versions stabilisées : à ce jour 3.10 → 3.13. Python 3.14 (trop récent) fait
# échouer `pip install` faute de wheels. On cherche donc un `python3.X` supporté,
# en préférant 3.12 (le plus éprouvé), avant de retomber sur `python3` générique.
pick_python() {
  # Un candidat convient si 3.10 <= version <= 3.13.
  local candidate
  for candidate in python3.12 python3.11 python3.13 python3.10 python3 python; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)
PY
    then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

# Un venv existant peut être invalide (créé par une tentative précédente avec un
# Python trop récent, ex. 3.14) : on le détecte et on le recrée si besoin.
venv_is_compatible() {
  [ -x "$VENV_DIR/bin/python" ] || return 1
  "$VENV_DIR/bin/python" - <<'PY' >/dev/null 2>&1
import sys
sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)
PY
}

if [ -d "$VENV_DIR" ] && ! venv_is_compatible; then
  echo "Environnement virtuel existant incompatible (mauvaise version de Python) — recréation..."
  rm -rf "$VENV_DIR"
fi

if [ ! -d "$VENV_DIR" ]; then
  PYTHON_BIN="$(pick_python)" || {
    echo "ERREUR : aucun Python compatible (3.10–3.13) trouvé." >&2
    echo "Python 3.14 est trop récent — PyTorch/numpy n'ont pas encore de binaires." >&2
    echo "Sur macOS :  brew install python@3.12   puis relancez ./run.sh" >&2
    echo "(Détecté : $(python3 --version 2>&1))" >&2
    exit 1
  }
  echo "Création de l'environnement virtuel avec $($PYTHON_BIN --version)..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
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
