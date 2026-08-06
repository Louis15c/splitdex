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
# Finitions proposées dans la fiche, telles qu'elles s'écrivent dans le titre et
# la description ("Lucanon reverse holo 66/217...").
#
# UNIQUEMENT holo et reverse : ce sont les seules vraies VARIATIONS, deux
# finitions d'une même carte (même numéro, même entrée de catalogue) que rien ne
# distingue dans les données — et que le foil ne permet pas de détecter sur
# photo, ne se voyant que sous le bon angle de lumière. Seul le vendeur, carte en
# main, peut trancher.
#
# Full art, promo, illustration rare... n'ont RIEN à faire ici : ce sont des
# cartes différentes, avec leur propre numéro et leur propre rareté — elles se
# déduisent donc automatiquement du catalogue (voir RARITY_DISPLAY_FR).
# "reverse rocket" : le reverse spécifique des sets Team Rocket, que les
# collectionneurs nomment ainsi plutôt que "reverse holo".
LISTING_VARIANTS = ["", "holo", "reverse holo", "reverse rocket"]
# Proposition complète insérée en fin de description, reprise des annonces
# réelles ("carte sortie de booster, en état comme neuf"). La mention "sortie de
# booster" est une affirmation de provenance : à retirer ici si le stock vient
# d'ailleurs (achat à l'unité, lot d'occasion).
CONDITION_PHRASES = {
    "Neuf": "carte sortie de booster, en état neuf",
    "Très bon état": "carte sortie de booster, en état comme neuf",
    "Bon état": "carte en bon état",
    "Satisfaisant": "carte en état satisfaisant",
}

# Hashtag de fin d'annonce identifiant la boutique (`#collection #{SHOP_HASHTAG}`),
# à adapter si le pseudo Vinted change.
SHOP_HASHTAG = "tonio28"

# Annonces reprises depuis Vinted pour être republiées (photos + texte).
REPUBLISH_DIR = DATA_DIR / "republish"
# Recadrage appliqué aux photos reprises, en fraction de chaque côté : 2% rogne
# les bords sans toucher au sujet. C'est une retouche de cadrage ordinaire,
# ajustable ou désactivable (0) depuis la fiche.
REPUBLISH_CROP_RATIO = 0.02

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
