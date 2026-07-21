import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
CROPS_DIR = UPLOADS_DIR / "crops"
DB_DIR = DATA_DIR / "db"
REFERENCE_THUMBNAILS_DIR = DB_DIR / "reference_thumbnails"

FRONTEND_DIR = PROJECT_ROOT / "frontend"
TEMPLATES_DIR = PROJECT_ROOT / "templates"

SQLITE_PATH = DB_DIR / "splitdex.sqlite3"

DEFAULT_LISTING_CONDITION = "Très bon état"
# Catégories réelles de l'état Vinted (constaté sur de vraies annonces).
LISTING_CONDITIONS = ["Neuf", "Très bon état", "Bon état", "Satisfaisant"]
# Phrase insérée dans la description pour chaque état, ex: "carte en bon état".
CONDITION_PHRASES = {
    "Neuf": "état neuf",
    "Très bon état": "très bon état",
    "Bon état": "bon état",
    "Satisfaisant": "mauvais état",
}

# Hashtag de fin d'annonce identifiant la boutique (`#collection #{SHOP_HASHTAG}`),
# à adapter si le pseudo Vinted change.
SHOP_HASHTAG = "tonio28"

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
# Nombre maximum de photos par envoi (cas d'usage : une rafale de photos de
# cartes unitaires). Garde-fou raisonnable pour une app LAN mono-utilisateur :
# assez large pour un lot de scans, assez serré pour éviter un envoi
# accidentel de toute une galerie.
MAX_PHOTOS_PER_BATCH = 20

# pokemontcg.io : fonctionne sans clé (rate-limit strict) ou avec une clé
# gratuite (https://pokemontcg.io) posée dans un fichier .env à la racine du
# projet (POKEMONTCG_API_KEY=...), non versionné.
POKEMONTCG_API_BASE_URL = "https://api.pokemontcg.io/v2"
POKEMONTCG_API_KEY = os.environ.get("POKEMONTCG_API_KEY")

# Roboflow : uniquement utilisé pour télécharger le dataset d'entraînement du
# modèle de détection (backend/app/scripts/train_card_yolo.py), une seule
# fois. Clé gratuite sur https://roboflow.com, posée dans .env
# (ROBOFLOW_API_KEY=...), non versionné. Pas utilisé à l'exécution normale.
ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY")

MODELS_DIR = DATA_DIR / "models"
CARD_YOLO_MODEL_PATH = MODELS_DIR / "card_detector.pt"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
CROPS_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)
REFERENCE_THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
