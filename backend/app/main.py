import threading

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.crops import router as crops_router
from app.api.identify import router as identify_router
from app.api.listings import router as listings_router
from app.api.reference import router as reference_router
from app.api.republish import router as republish_router
from app.api.uploads import router as uploads_router
from app.api.vinted import router as vinted_router
from app.core.config import FRONTEND_DIR, REFERENCE_THUMBNAILS_DIR, UPLOADS_DIR
from app.core.db import init_db

app = FastAPI(title="Splitdex", version="0.1.0")

init_db()

# Préchauffage du modèle YOLO en arrière-plan : le chargement des poids +
# la première inférence coûtent ~3s, autant les payer au démarrage du serveur
# plutôt qu'au premier clic "Découper" de l'utilisateur.
from app.core.card_detector_yolo import warmup as _warmup_yolo  # noqa: E402

threading.Thread(target=_warmup_yolo, daemon=True).start()

# Préchauffage du modèle d'embeddings DINOv2 (repli d'identification foil/gold) :
# son chargement coûte ~50s, à payer au démarrage plutôt qu'à la première carte
# difficile. Seulement si l'index d'embeddings a été construit (sinon inutile).
from app.core.card_identifier import EMBEDDINGS_PATH  # noqa: E402


def _warmup_embedder():
    if EMBEDDINGS_PATH.exists():
        from app.core.card_embedder import is_available

        is_available()


threading.Thread(target=_warmup_embedder, daemon=True).start()

app.include_router(uploads_router)
app.include_router(crops_router)
app.include_router(identify_router)
app.include_router(reference_router)
app.include_router(listings_router)
app.include_router(vinted_router)
app.include_router(republish_router)

# Photos uploadées, servies telles quelles pour prévisualisation
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# Miniatures des cartes de référence (cache pokemontcg.io), pour affichage cote à cote
app.mount("/reference-images", StaticFiles(directory=REFERENCE_THUMBNAILS_DIR), name="reference-images")

# Frontend statique (JS vanille), pas de build requis
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


# Pages de l'application (frontend multi-pages sans build) : URLs propres qui
# servent les fichiers statiques correspondants. Le paramètre de session est
# lu côté client depuis la query string (ex: /scan?s=<id>).
@app.get("/scan")
async def scan_page():
    return FileResponse(FRONTEND_DIR / "scan.html")


@app.get("/history")
async def history_page():
    return FileResponse(FRONTEND_DIR / "history.html")


@app.get("/vinted")
async def vinted_page():
    return FileResponse(FRONTEND_DIR / "vinted.html")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
