from fastapi import APIRouter, Query

from app.core.config import LISTING_CONDITIONS, LISTING_VARIANTS
from app.core.db import db_cursor
from app.core.pokemon_names_fr import (
    POKEMON_NAME_EN_BY_NORMALIZED_FR,
    normalize_name,
    translate_card_name_to_fr,
)

router = APIRouter(prefix="/api/reference", tags=["reference"])

SEARCH_LIMIT = 20
# Nombre maximum d'espèces anglaises injectées dans la requête quand la
# recherche matche des noms français (ex: "pi" matcherait beaucoup d'espèces).
MAX_FRENCH_HINTS = 10


@router.get("/status")
def reference_status():
    with db_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS count FROM reference_cards")
        count = cursor.fetchone()["count"]
    return {"cached_cards": count}


@router.get("/conditions")
def list_conditions():
    return LISTING_CONDITIONS


@router.get("/variants")
def list_variants():
    """Finitions proposées dans la fiche (holo, reverse holo...) — voir
    LISTING_VARIANTS : elles se renseignent à la main, carte en main."""
    return LISTING_VARIANTS


@router.get("/search")
def search_reference_cards(q: str = Query(min_length=2)):
    """Recherche par nom, en anglais **ou en français** : le cache
    (pokemontcg.io) ne stocke que les noms anglais, mais la table
    `pokemon_names_fr.py` permet de traduire la requête — chercher
    "Carapuce" trouve les cartes "Squirtle" (et leurs variantes suffixées,
    via une correspondance par préfixe)."""
    normalized_q = normalize_name(q)
    english_hints = [
        name_en
        for fr_normalized, name_en in POKEMON_NAME_EN_BY_NORMALIZED_FR.items()
        if normalized_q in fr_normalized
    ][:MAX_FRENCH_HINTS]

    clauses = ["name LIKE ? COLLATE NOCASE"]
    params: list = [f"%{q}%"]
    for name_en in english_hints:
        clauses.append("name LIKE ? COLLATE NOCASE")
        params.append(f"{name_en}%")
    params.append(SEARCH_LIMIT)

    with db_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id, name, set_name, number, rarity, small_image_url
            FROM reference_cards
            WHERE {" OR ".join(clauses)}
            ORDER BY name
            LIMIT ?
            """,
            params,
        )
        rows = cursor.fetchall()

    return [
        {
            "card_id": row["id"],
            # Nom affiché en français (public francophone) ; le card_id reste
            # la référence technique.
            "name": translate_card_name_to_fr(row["name"]),
            "set_name": row["set_name"],
            "number": row["number"],
            "rarity": row["rarity"],
            "image_url": f"/reference-images/{row['id']}.jpg",
        }
        for row in rows
    ]
