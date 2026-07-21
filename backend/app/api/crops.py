import json
from pathlib import Path

import cv2
from fastapi import APIRouter, HTTPException

from app.core.card_detector import detect_cards
from app.core.config import CROPS_DIR, UPLOADS_DIR
from app.core.validation import validate_photo_id

router = APIRouter(prefix="/api/photos", tags=["crops"])


def _find_photo_path(photo_id: str) -> Path:
    matches = [p for p in UPLOADS_DIR.glob(f"{photo_id}.*") if p.is_file()]
    if not matches:
        raise HTTPException(status_code=404, detail="Photo introuvable.")
    return matches[0]


def _meta_path(photo_id: str) -> Path:
    return CROPS_DIR / photo_id / "meta.json"


@router.post("/{photo_id}/crops")
def create_crops(photo_id: str):
    validate_photo_id(photo_id)
    photo_path = _find_photo_path(photo_id)
    image = cv2.imread(str(photo_path))
    if image is None:
        raise HTTPException(status_code=422, detail="Impossible de lire l'image.")

    detected_cards = detect_cards(image)
    if not detected_cards:
        raise HTTPException(
            status_code=422,
            detail="Aucune carte détectée. Vérifie l'éclairage et le contraste du fond.",
        )

    photo_crop_dir = CROPS_DIR / photo_id
    photo_crop_dir.mkdir(parents=True, exist_ok=True)
    for existing in photo_crop_dir.glob("card_*.jpg"):
        existing.unlink()

    crops_meta = []
    for card in detected_cards:
        filename = f"card_{card.index:02d}.jpg"
        cv2.imwrite(str(photo_crop_dir / filename), card.image)
        crops_meta.append(
            {
                "index": card.index,
                "filename": filename,
                "url": f"/uploads/crops/{photo_id}/{filename}",
                "corners": card.corners,
                "degraded": card.preset_index > 0,
            }
        )

    _meta_path(photo_id).write_text(json.dumps(crops_meta, ensure_ascii=False, indent=2))
    return crops_meta


@router.get("/{photo_id}/crops")
def list_crops(photo_id: str):
    validate_photo_id(photo_id)
    meta_file = _meta_path(photo_id)
    if not meta_file.exists():
        return []
    return json.loads(meta_file.read_text())
