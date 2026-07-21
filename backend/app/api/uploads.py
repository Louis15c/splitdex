import uuid
from datetime import datetime, timezone

import aiofiles
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import (
    ALLOWED_IMAGE_TYPES,
    MAX_PHOTOS_PER_BATCH,
    MAX_UPLOAD_SIZE_BYTES,
    UPLOADS_DIR,
)

router = APIRouter(prefix="/api", tags=["uploads"])


def _extension_for(content_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }[content_type]


async def _save_photo(file: UploadFile) -> dict:
    """Enregistre un fichier en streaming (limite de taille vérifiée au fil
    de l'eau, pas après coup) et retourne sa fiche."""
    photo_id = str(uuid.uuid4())
    extension = _extension_for(file.content_type)
    dest_path = UPLOADS_DIR / f"{photo_id}{extension}"

    size = 0
    async with aiofiles.open(dest_path, "wb") as out_file:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE_BYTES:
                await out_file.close()
                dest_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"{file.filename} : fichier trop volumineux "
                    f"(max {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} Mo).",
                )
            await out_file.write(chunk)

    return {
        "id": photo_id,
        "filename": dest_path.name,
        "original_filename": file.filename,
        "url": f"/uploads/{dest_path.name}",
        "size_bytes": size,
        "content_type": file.content_type,
    }


@router.post("/upload")
async def upload_photos(files: list[UploadFile] = File(...)):
    """Upload d'une ou plusieurs photos en un envoi (cas d'usage : une rafale
    de photos de cartes unitaires). Les types sont validés pour tout le lot
    AVANT d'écrire quoi que ce soit — soit le lot est cohérent, soit rien
    n'est enregistré, pour éviter les états à moitié réussis difficiles à
    expliquer à l'utilisateur. Seule la limite de taille, vérifiable
    uniquement en cours de lecture, peut interrompre un lot en route."""
    if len(files) > MAX_PHOTOS_PER_BATCH:
        raise HTTPException(
            status_code=413,
            detail=f"Trop de photos d'un coup ({len(files)}) : maximum "
            f"{MAX_PHOTOS_PER_BATCH} par envoi.",
        )

    invalid = [file.filename for file in files if file.content_type not in ALLOWED_IMAGE_TYPES]
    if invalid:
        raise HTTPException(
            status_code=415,
            detail=f"Type de fichier non supporté pour : {', '.join(invalid)}. "
            f"Formats acceptés : JPEG, PNG, WEBP.",
        )

    photos = []
    for file in files:
        photos.append(await _save_photo(file))

    return {"photos": photos}


@router.get("/uploads")
def list_uploads():
    photos = []
    for path in sorted(UPLOADS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file() or path.name.startswith("."):
            continue
        stat = path.stat()
        photos.append(
            {
                "id": path.stem,
                "filename": path.name,
                "url": f"/uploads/{path.name}",
                "size_bytes": stat.st_size,
                "uploaded_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    return photos
