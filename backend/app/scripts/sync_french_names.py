"""Renseigne le nom OFFICIEL français de chaque carte, depuis TCGdex.

pokemontcg.io ne publie que l'anglais. Jusqu'ici le français était reconstruit
en remplaçant le nom d'espèce dans le nom anglais — approximation qui produit
des noms qui n'existent pas ("Team Rocket's Taupiqueur" au lieu de "Taupiqueur
de la Team Rocket", "Carchacrok ex" au lieu de "Carchacrok-ex").

TCGdex publie, lui, les noms officiels. Un appel par SET suffit (et non un par
carte) : `/v2/fr/sets/{id}` renvoie toutes ses cartes avec leur nom français.

Les cartes absentes du catalogue français restent à NULL : la génération
retombe alors sur la traduction reconstruite, comme avant.

Idempotent : relançable, il réécrit simplement les noms.

Usage : python -m app.scripts.sync_french_names
"""

import gzip
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

from app.core.config import DB_DIR
from app.core.db import init_db
from app.core.tcgdex_set_ids import SET_TCGDEX_ID

SET_URL = "https://api.tcgdex.net/v2/fr/sets/{set_id}"
# Noms embarqués dans le dépôt : la synchronisation est ainsi instantanée et
# hors ligne sur une nouvelle machine (121 Ko), le réseau ne servant qu'à
# rafraîchir le lot avec `--refresh`.
BUNDLE_PATH = Path(__file__).resolve().parent.parent / "data" / "french_names.json.gz"
_UA = {"User-Agent": "Mozilla/5.0 (Splitdex)"}


def _fetch_set(set_id: str) -> dict | None:
    try:
        request = urllib.request.Request(SET_URL.format(set_id=set_id), headers=_UA)
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except Exception:
        return None


def _normalize(number: str) -> str:
    return str(number).lstrip("0") or "0"


def _load_bundle() -> list | None:
    if not BUNDLE_PATH.exists():
        return None
    with gzip.open(BUNDLE_PATH, "rt", encoding="utf-8") as bundle:
        return json.load(bundle)


def _save_bundle(pairs: list) -> None:
    BUNDLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(BUNDLE_PATH, "wt", encoding="utf-8", compresslevel=9) as bundle:
        json.dump(pairs, bundle, ensure_ascii=False, separators=(",", ":"))


def main() -> None:
    init_db()
    if "--refresh" not in sys.argv:
        pairs = _load_bundle()
        if pairs is not None:
            connection = sqlite3.connect(str(DB_DIR / "splitdex.sqlite3"))
            connection.executemany(
                "UPDATE reference_cards SET name_fr = ? WHERE id = ?",
                [(name, card_id) for card_id, name in pairs],
            )
            connection.commit()
            covered = connection.execute(
                "SELECT COUNT(*) FROM reference_cards WHERE name_fr IS NOT NULL"
            ).fetchone()[0]
            print(f"Noms français officiels : {covered} cartes (lot embarqué).")
            print("Pour re-interroger TCGdex : --refresh")
            return
        print("Lot embarqué absent, interrogation de TCGdex…")  # garantit la présence de la colonne name_fr (migration)
    connection = sqlite3.connect(str(DB_DIR / "splitdex.sqlite3"))
    connection.row_factory = sqlite3.Row
    our_sets = [row["set_id"] for row in connection.execute(
        "SELECT DISTINCT set_id FROM reference_cards ORDER BY set_id"
    )]

    total_named, sets_without_french = 0, []
    for set_id in our_sets:
        payload = _fetch_set(SET_TCGDEX_ID.get(set_id, set_id))
        cards = (payload or {}).get("cards") or []
        if not cards:
            sets_without_french.append(set_id)
            continue

        named = 0
        for card in cards:
            name_fr = card.get("name")
            if not name_fr:
                continue
            # Nos numéros n'ont pas les zéros de tête de TCGdex ("066" -> "66").
            cursor = connection.execute(
                "UPDATE reference_cards SET name_fr = ? WHERE set_id = ? AND number = ?",
                (name_fr, set_id, _normalize(card["localId"])),
            )
            named += cursor.rowcount
        connection.commit()
        total_named += named
        print(f"  {set_id:12} {named:4} noms", flush=True)

    total = connection.execute("SELECT COUNT(*) FROM reference_cards").fetchone()[0]
    covered = connection.execute(
        "SELECT COUNT(*) FROM reference_cards WHERE name_fr IS NOT NULL"
    ).fetchone()[0]
    _save_bundle([[row["id"], row["name_fr"]] for row in connection.execute(
        "SELECT id, name_fr FROM reference_cards WHERE name_fr IS NOT NULL ORDER BY id")])
    print(f"\nNoms français officiels : {covered}/{total} cartes (lot mis à jour)")
    if sets_without_french:
        print(f"Sets absents du catalogue français ({len(sets_without_french)}) : "
              f"{', '.join(sets_without_french)}")


if __name__ == "__main__":
    main()
