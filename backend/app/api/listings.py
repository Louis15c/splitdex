import io
import re
import sqlite3
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import CROPS_DIR, DEFAULT_LISTING_CONDITION
from app.core.db import db_cursor
from app.core.description_generator import generate_listing_text
from app.core.card_translations import translate_set_name
from app.core.pokemon_names_fr import translate_card_name_to_fr
from app.core.price_estimator import estimate_price
from app.core.validation import validate_crop_filename, validate_photo_id

router = APIRouter(prefix="/api/photos", tags=["listings"])


class ListingUpdate(BaseModel):
    card_id: str | None = None
    condition: str | None = None
    price: float | None = None
    language: str | None = None
    title: str | None = None
    description: str | None = None


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\-À-ÿ]+", "_", name).strip("_") or "carte"


def _get_reference_card(cursor: sqlite3.Cursor, card_id: str) -> sqlite3.Row | None:
    cursor.execute(
        "SELECT set_id, name, set_name, series, number, printed_total, rarity FROM reference_cards WHERE id = ?",
        (card_id,),
    )
    return cursor.fetchone()


def _serialize_listing(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict:
    card = _get_reference_card(cursor, row["card_id"])
    return {
        "crop_filename": row["crop_filename"],
        "card_id": row["card_id"],
        "card_name": translate_card_name_to_fr(card["name"]) if card else None,
        "set_name": translate_set_name(card["set_name"], card["set_id"]) if card else None,
        "number": card["number"] if card else None,
        "rarity": card["rarity"] if card else None,
        "image_url": f"/reference-images/{row['card_id']}.jpg",
        "condition": row["condition"],
        "price": row["price"],
        "language": row["language"],
        "title": row["title"],
        "description": row["description"],
    }


@router.post("/{photo_id}/listings/generate")
def generate_listings(photo_id: str):
    validate_photo_id(photo_id)
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT crop_filename, card_id, language FROM identifications WHERE photo_id = ?",
            (photo_id,),
        )
        identifications = cursor.fetchall()

        if not identifications:
            raise HTTPException(
                status_code=404,
                detail="Aucune identification trouvée pour cette photo. Lance d'abord l'identification.",
            )

        results = []
        for identification in identifications:
            if identification["card_id"] is None:
                continue

            card = _get_reference_card(cursor, identification["card_id"])
            if card is None:
                continue

            listing_text = generate_listing_text(dict(card), language=identification["language"])

            cursor.execute(
                """
                INSERT INTO listings
                    (photo_id, crop_filename, card_id, condition, price, language, title, description, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(photo_id, crop_filename) DO UPDATE SET
                    card_id=excluded.card_id, language=excluded.language, title=excluded.title,
                    description=excluded.description, updated_at=excluded.updated_at
                """,
                (
                    photo_id,
                    identification["crop_filename"],
                    identification["card_id"],
                    DEFAULT_LISTING_CONDITION,
                    None,
                    identification["language"],
                    listing_text["title"],
                    listing_text["description"],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

            cursor.execute(
                "SELECT * FROM listings WHERE photo_id = ? AND crop_filename = ?",
                (photo_id, identification["crop_filename"]),
            )
            results.append(_serialize_listing(cursor, cursor.fetchone()))

    return results


@router.get("/{photo_id}/listings")
def get_listings(photo_id: str):
    validate_photo_id(photo_id)
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM listings WHERE photo_id = ?", (photo_id,))
        rows = cursor.fetchall()
        return [_serialize_listing(cursor, row) for row in rows]


@router.patch("/{photo_id}/listings/{crop_filename}")
def update_listing(photo_id: str, crop_filename: str, update: ListingUpdate):
    validate_photo_id(photo_id)
    validate_crop_filename(crop_filename)
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM listings WHERE photo_id = ? AND crop_filename = ?",
            (photo_id, crop_filename),
        )
        existing = cursor.fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Fiche introuvable pour cette carte.")

        if update.card_id is not None and _get_reference_card(cursor, update.card_id) is None:
            raise HTTPException(status_code=400, detail="Carte de référence inconnue.")

        merged = {
            "card_id": update.card_id if update.card_id is not None else existing["card_id"],
            "condition": update.condition if update.condition is not None else existing["condition"],
            "price": update.price if update.price is not None else existing["price"],
            "language": update.language if update.language is not None else existing["language"],
            "title": update.title if update.title is not None else existing["title"],
            "description": update.description if update.description is not None else existing["description"],
        }

        cursor.execute(
            """
            UPDATE listings SET card_id=?, condition=?, price=?, language=?, title=?, description=?, updated_at=?
            WHERE photo_id=? AND crop_filename=?
            """,
            (
                merged["card_id"],
                merged["condition"],
                merged["price"],
                merged["language"],
                merged["title"],
                merged["description"],
                datetime.now(timezone.utc).isoformat(),
                photo_id,
                crop_filename,
            ),
        )

        cursor.execute(
            "SELECT * FROM listings WHERE photo_id = ? AND crop_filename = ?",
            (photo_id, crop_filename),
        )
        return _serialize_listing(cursor, cursor.fetchone())


@router.post("/{photo_id}/listings/{crop_filename}/regenerate")
def regenerate_listing(photo_id: str, crop_filename: str):
    validate_photo_id(photo_id)
    validate_crop_filename(crop_filename)
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM listings WHERE photo_id = ? AND crop_filename = ?",
            (photo_id, crop_filename),
        )
        listing = cursor.fetchone()
        if listing is None:
            raise HTTPException(status_code=404, detail="Fiche introuvable pour cette carte.")

        card = _get_reference_card(cursor, listing["card_id"])
        if card is None:
            raise HTTPException(status_code=404, detail="Carte de référence introuvable.")

        listing_text = generate_listing_text(
            dict(card),
            condition=listing["condition"],
            language=listing["language"],
        )

        cursor.execute(
            """
            UPDATE listings SET title=?, description=?, updated_at=?
            WHERE photo_id=? AND crop_filename=?
            """,
            (
                listing_text["title"],
                listing_text["description"],
                datetime.now(timezone.utc).isoformat(),
                photo_id,
                crop_filename,
            ),
        )

        cursor.execute(
            "SELECT * FROM listings WHERE photo_id = ? AND crop_filename = ?",
            (photo_id, crop_filename),
        )
        return _serialize_listing(cursor, cursor.fetchone())


@router.get("/{photo_id}/listings/{crop_filename}/price-estimate")
def get_price_estimate(photo_id: str, crop_filename: str):
    validate_photo_id(photo_id)
    validate_crop_filename(crop_filename)
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM listings WHERE photo_id = ? AND crop_filename = ?",
            (photo_id, crop_filename),
        )
        listing = cursor.fetchone()
        if listing is None:
            raise HTTPException(status_code=404, detail="Fiche introuvable pour cette carte.")

        card = _get_reference_card(cursor, listing["card_id"])
        if card is None:
            raise HTTPException(status_code=404, detail="Carte de référence introuvable.")

    estimate = estimate_price(
        card["name"],
        card["number"],
        listing["language"],
        rarity=card["rarity"],
        card_id=listing["card_id"],
        set_id=card["set_id"],
    )
    if estimate is None:
        raise HTTPException(
            status_code=404,
            detail="Aucune estimation de prix disponible pour cette carte (non couverte par TCGdex).",
        )

    return {
        "suggested": estimate.suggested,
        "trend": estimate.trend,
        "avg30": estimate.avg30,
        "avg": estimate.avg,
        "low": estimate.low,
        "currency": estimate.currency,
        "source_language": estimate.source_language,
        "note": estimate.note,
    }


@router.get("/{photo_id}/export")
def export_listings(photo_id: str):
    validate_photo_id(photo_id)
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM listings WHERE photo_id = ?", (photo_id,))
        rows = cursor.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="Aucune fiche à exporter pour cette photo.")

        listings = [_serialize_listing(cursor, row) for row in rows]

    photo_crop_dir = CROPS_DIR / photo_id
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for i, listing in enumerate(listings, start=1):
            base_name = f"{i:02d}_{_sanitize_filename(listing['card_name'] or listing['card_id'])}"

            crop_path = photo_crop_dir / listing["crop_filename"]
            if crop_path.exists():
                zip_file.write(crop_path, arcname=f"{base_name}.jpg")

            # État/prix ne sont pas ré-ajoutés ici : ils sont déjà dans la description
            # (via le gabarit) tant que "Régénérer le texte" a été utilisé après une
            # modification — sinon le texte affiché peut être en décalage avec ces
            # champs, voir le rappel dans l'interface.
            text_content = (
                f"Titre\n-----\n{listing['title']}\n\n"
                f"Description\n-----------\n{listing['description']}\n"
            )
            zip_file.writestr(f"{base_name}.txt", text_content)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="splitdex_{photo_id}.zip"'},
    )
