#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_ROOT/backend/.venv"
# Écoute sur la boucle locale par défaut : le serveur n'a aucune
# authentification et sert vos photos et annonces. Sur un réseau partagé (wifi
# public, colocation), « 0.0.0.0 » l'exposerait à tout le monde.
# Pour y accéder depuis un autre appareil du réseau : SPLITDEX_HOST=0.0.0.0 ./run.sh
HOST="${SPLITDEX_HOST:-127.0.0.1}"
PORT="${SPLITDEX_PORT:-8000}"

# Sélection d'un interpréteur Python compatible.
# PyTorch, numpy & co. ne publient leurs binaires (« wheels ») que pour des
# versions stabilisées. On vise 3.10 → 3.12 : borne haute fixée par numpy 1.26
# (requis pour le torch de Mac Intel, cf. requirements.txt) qui n'a pas de wheel
# pour 3.13, et borne basse par les dépendances. Python 3.13/3.14 (trop récents)
# font échouer `pip install`. On cherche un `python3.X` supporté, en préférant
# 3.12 (le plus éprouvé), avant de retomber sur `python3` générique.
pick_python() {
  # Un candidat convient si 3.10 <= version <= 3.12.
  local candidate
  for candidate in python3.12 python3.11 python3.10 python3 python; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)
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
sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)
PY
}

# ── Dépendances système (hors pip) ────────────────────────────────────────
# requirements.txt ne gère que les paquets Python. Python lui-même et Tesseract
# (OCR + packs de langue, indispensables à la détection de langue) relèvent du
# gestionnaire système. Sur macOS avec Homebrew, on les installe automatiquement
# s'ils manquent ; sur Linux on affiche la commande apt (installation manuelle,
# car elle exige sudo).
ensure_python() {
  pick_python >/dev/null 2>&1 && return 0
  if command -v brew >/dev/null 2>&1; then
    echo "Python 3.10–3.12 introuvable — installation de python@3.12 via Homebrew..."
    brew install python@3.12 || true
  fi
  pick_python >/dev/null 2>&1
}

tesseract_ready() {
  command -v tesseract >/dev/null 2>&1 || return 1
  # Le pack français doit être présent, sinon les packs de langue manquent.
  tesseract --list-langs 2>/dev/null | grep -qx fra
}

ensure_tesseract() {
  tesseract_ready && return 0
  if command -v brew >/dev/null 2>&1; then
    echo "Tesseract (ou ses packs de langue) manquant — installation via Homebrew..."
    brew install tesseract tesseract-lang || \
      echo "⚠️  Échec de l'installation de Tesseract — la détection de langue sera désactivée." >&2
  else
    echo "⚠️  Tesseract absent : la détection de langue sera désactivée (le reste fonctionne)." >&2
    echo "    Linux : sudo apt install -y tesseract-ocr tesseract-ocr-fra tesseract-ocr-jpn \\" >&2
    echo "                                tesseract-ocr-deu tesseract-ocr-spa tesseract-ocr-ita" >&2
  fi
}

# Garantir Python AVANT de créer le venv ; Tesseract est optionnel (non bloquant).
if ! ensure_python; then
  echo "ERREUR : aucun Python compatible (3.10–3.12) trouvé, installation auto impossible." >&2
  echo "Installez-le :  macOS  brew install python@3.12   |   Linux  apt install python3 python3-venv" >&2
  echo "(Détecté : $(python3 --version 2>&1 || echo 'python3 absent'))" >&2
  exit 1
fi
ensure_tesseract || true

if [ -d "$VENV_DIR" ] && ! venv_is_compatible; then
  echo "Environnement virtuel existant incompatible (mauvaise version de Python) — recréation..."
  rm -rf "$VENV_DIR"
fi

if [ ! -d "$VENV_DIR" ]; then
  PYTHON_BIN="$(pick_python)" || {
    echo "ERREUR : aucun Python compatible (3.10–3.12) trouvé." >&2
    echo "Python 3.13/3.14 sont trop récents — numpy 1.26 (requis) n'a pas de binaires." >&2
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
if [ "$HOST" = "0.0.0.0" ]; then
  echo "Splitdex démarre sur http://localhost:$PORT"
  echo "Ouvert au réseau — depuis un autre appareil du LAN :"
  echo "  http://${LOCAL_IP:-<adresse-ip-locale>}:$PORT"
else
  echo "Splitdex démarre sur http://$HOST:$PORT (cette machine uniquement)"
  echo "Pour l'ouvrir au réseau local : SPLITDEX_HOST=0.0.0.0 ./run.sh"
fi
echo ""

cd "$PROJECT_ROOT/backend"
exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
