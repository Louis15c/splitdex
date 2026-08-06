"""Reprise d'une annonce Vinted existante pour la republier sans tout ressaisir.

Le flux reste manuel de bout en bout, comme le remplissage de formulaire (voir
`vinted.py`) : c'est l'utilisateur qui ouvre SON annonce, clique pour la
reprendre, puis publie lui-même la nouvelle. Rien n'est fait à son insu, rien
n'est publié automatiquement.

1. Sur la page d'une de ses annonces, le userscript lit titre, prix,
   description, état et l'adresse des photos, et les envoie ici.
2. Ce module télécharge les photos, les **recadre** (rognage léger des bords,
   cf. `REPUBLISH_CROP_RATIO`) et les range dans `data/republish/{id}/`.
3. L'utilisateur récupère les photos (ZIP), envoie la fiche vers le formulaire
   Vinted par la mécanique existante, ajoute les photos et publie.
"""

import io
import json
import re
import shutil
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.core.config import REPUBLISH_CROP_RATIO, REPUBLISH_DIR

router = APIRouter(prefix="/api/republish", tags=["republish"])

MAX_PHOTOS = 20
PHOTO_TIMEOUT = 20
_UA = {"User-Agent": "Mozilla/5.0 (Splitdex)"}
_ID_PATTERN = re.compile(r"^[a-f0-9-]{36}$")


class CapturedListing(BaseModel):
    title: str
    description: str = ""
    price: float | None = None
    condition: str | None = None
    photo_urls: list[str] = []
    source_url: str | None = None


def _entry_dir(entry_id: str):
    if not _ID_PATTERN.match(entry_id):
        raise HTTPException(status_code=400, detail="Identifiant invalide.")
    directory = REPUBLISH_DIR / entry_id
    if not directory.is_dir():
        raise HTTPException(status_code=404, detail="Annonce reprise introuvable.")
    return directory


def _crop_borders(image: np.ndarray, ratio: float) -> np.ndarray:
    """Rogne une même fraction sur les quatre côtés — un recadrage, pas un
    redimensionnement : le sujet garde ses proportions."""
    if ratio <= 0:
        return image
    height, width = image.shape[:2]
    margin_y, margin_x = int(height * ratio), int(width * ratio)
    if height - 2 * margin_y < 50 or width - 2 * margin_x < 50:
        return image  # image trop petite pour être rognée utilement
    return image[margin_y : height - margin_y, margin_x : width - margin_x]


def _download_photo(url: str) -> bytes | None:
    try:
        request = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(request, timeout=PHOTO_TIMEOUT) as response:
            return response.read()
    except Exception:
        return None


@router.post("")
def capture_listing(listing: CapturedListing):
    """Reçoit une annonce reprise et prépare ses photos recadrées."""
    entry_id = str(uuid.uuid4())
    directory = REPUBLISH_DIR / entry_id
    directory.mkdir(parents=True, exist_ok=True)

    saved = []
    for index, url in enumerate(listing.photo_urls[:MAX_PHOTOS]):
        data = _download_photo(url)
        if data is None:
            continue
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            continue
        filename = f"photo_{index:02d}.jpg"
        cv2.imwrite(
            str(directory / filename),
            _crop_borders(image, REPUBLISH_CROP_RATIO),
            [cv2.IMWRITE_JPEG_QUALITY, 95],
        )
        saved.append(filename)

    meta = {
        "id": entry_id,
        "title": listing.title,
        "description": listing.description,
        "price": listing.price,
        "condition": listing.condition,
        "source_url": listing.source_url,
        "photos": saved,
        "photos_requested": len(listing.photo_urls),
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    (directory / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta


@router.get("")
def list_captured():
    """Annonces reprises, la plus récente d'abord."""
    if not REPUBLISH_DIR.is_dir():
        return []
    entries = []
    for meta_path in REPUBLISH_DIR.glob("*/meta.json"):
        try:
            entries.append(json.loads(meta_path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return sorted(entries, key=lambda entry: entry.get("captured_at", ""), reverse=True)


@router.get("/{entry_id}/photos/{filename}")
def get_photo(entry_id: str, filename: str):
    directory = _entry_dir(entry_id)
    if not re.match(r"^photo_\d{2}\.jpg$", filename):
        raise HTTPException(status_code=400, detail="Nom de photo invalide.")
    path = directory / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Photo introuvable.")
    return FileResponse(path)


@router.get("/{entry_id}/photos.zip")
def download_photos(entry_id: str):
    """Toutes les photos recadrées, prêtes à être re-téléversées sur Vinted."""
    directory = _entry_dir(entry_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.glob("photo_*.jpg")):
            archive.write(path, path.name)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="photos_{entry_id[:8]}.zip"'},
    )


@router.delete("/{entry_id}")
def delete_captured(entry_id: str):
    shutil.rmtree(_entry_dir(entry_id))
    return {"status": "ok"}
