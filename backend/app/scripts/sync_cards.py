"""Synchronise le cache local de cartes de référence depuis pokemontcg.io.

Usage (depuis backend/, venv activé) :
    python -m app.scripts.sync_cards
    python -m app.scripts.sync_cards --limit 200   # test rapide
    python -m app.scripts.sync_cards --force        # re-télécharge tout

Le script est idempotent et reprenable : les cartes déjà présentes en cache
sont sautées (sauf --force), donc une synchronisation interrompue peut être
relancée sans tout refaire.

Sans clé API pokemontcg.io (POKEMONTCG_API_KEY dans .env), la récupération
des métadonnées est fortement limitée en débit (l'appel API intègre un
backoff automatique sur les réponses 429). Le téléchargement des images
(pour le hash perceptuel) se fait en parallèle car il ne passe pas par la
même API et n'est pas soumis à la même limite.
"""

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import httpx

from app.core.config import REFERENCE_THUMBNAILS_DIR
from app.core.db import db_cursor, init_db
from app.core.phash import compute_phash_from_bytes
from app.core.pokemontcg_client import PAGE_SIZE, iter_all_cards

DOWNLOAD_CONCURRENCY = 8


def _already_synced(card_id: str) -> bool:
    with db_cursor() as cursor:
        cursor.execute("SELECT 1 FROM reference_cards WHERE id = ?", (card_id,))
        return cursor.fetchone() is not None


def _download_and_hash(client: httpx.Client, card: dict) -> str | None:
    small_url = card["images"]["small"]
    for attempt in range(3):
        try:
            response = client.get(small_url, timeout=60.0)
            response.raise_for_status()
            break
        except httpx.HTTPError:
            if attempt == 2:
                return None
            time.sleep(2**attempt * 2)
    else:
        return None

    thumbnail_path = REFERENCE_THUMBNAILS_DIR / f"{card['id']}.jpg"
    thumbnail_path.write_bytes(response.content)

    return compute_phash_from_bytes(response.content)


def _upsert_card(card: dict, phash: str) -> None:
    set_info = card.get("set", {})
    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO reference_cards
                (id, name, set_id, set_name, series, number, printed_total, rarity,
                 small_image_url, large_image_url, phash, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, set_id=excluded.set_id, set_name=excluded.set_name,
                series=excluded.series,
                number=excluded.number, printed_total=excluded.printed_total,
                rarity=excluded.rarity, small_image_url=excluded.small_image_url,
                large_image_url=excluded.large_image_url, phash=excluded.phash,
                synced_at=excluded.synced_at
            """,
            (
                card["id"],
                card.get("name", ""),
                set_info.get("id", ""),
                set_info.get("name", ""),
                set_info.get("series"),
                card.get("number", ""),
                set_info.get("printedTotal"),
                card.get("rarity"),
                card["images"]["small"],
                card["images"].get("large"),
                phash,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def sync(force: bool = False, limit: int | None = None) -> None:
    init_db()

    print("Récupération des métadonnées du catalogue pokemontcg.io...")
    all_cards = []
    for card in iter_all_cards():
        all_cards.append(card)
        if len(all_cards) % PAGE_SIZE == 0:
            print(f"  ... {len(all_cards)} cartes récupérées jusqu'ici")
        if limit is not None and len(all_cards) >= limit:
            break
    print(f"{len(all_cards)} cartes au catalogue (avant filtrage du cache existant).")

    to_process = [c for c in all_cards if force or not _already_synced(c["id"])]
    skipped = len(all_cards) - len(to_process)
    print(f"{skipped} déjà en cache, {len(to_process)} à télécharger et hasher.")

    processed = 0
    failed = 0
    start = time.time()

    with httpx.Client() as client, ThreadPoolExecutor(max_workers=DOWNLOAD_CONCURRENCY) as executor:
        futures = {executor.submit(_download_and_hash, client, card): card for card in to_process}
        for future in as_completed(futures):
            card = futures[future]
            phash = future.result()
            if phash is None:
                failed += 1
                print(f"  échec téléchargement : {card['id']} ({card.get('name')})")
                continue

            _upsert_card(card, phash)
            processed += 1

            if processed % 100 == 0:
                elapsed = time.time() - start
                rate = processed / elapsed if elapsed > 0 else 0
                print(f"  {processed}/{len(to_process)} traitées ({rate:.1f}/s, {failed} échecs)")

    elapsed = time.time() - start
    print(
        f"Terminé : {processed} synchronisées, {skipped} déjà en cache, "
        f"{failed} échecs, en {elapsed:.0f}s"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-télécharge même les cartes déjà en cache")
    parser.add_argument("--limit", type=int, default=None, help="Limite le nombre de cartes traitées (tests)")
    args = parser.parse_args()
    sync(force=args.force, limit=args.limit)
