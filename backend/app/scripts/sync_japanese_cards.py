"""Synchronise le catalogue JAPONAIS (TCGdex, locale `ja`) dans `japanese_cards`.

Une carte japonaise porte un numéro et une extension différents de l'édition
internationale : la Posipi référencée "193/182 Faille Paradoxe" chez
pokemontcg.io est vendue "65/62 レイジングサーフ" au Japon. Un vendeur annonce la
référence imprimée sur SA carte — il faut donc connaître les deux catalogues.

Seules les MÉTADONNÉES sont récupérées ici (un appel par set, ~177 requêtes) :
les images ne sont téléchargées qu'à la demande, au moment d'apparier une carte
précise (voir `japanese_matcher`), ce qui évite de rapatrier 16 000 visuels dont
la quasi-totalité ne servira jamais.

Idempotent : relançable, il réécrit les lignes existantes.

Usage : python -m app.scripts.sync_japanese_cards
"""

import json
import sqlite3
import urllib.request

from app.core.config import DB_DIR
from app.core.db import init_db

SETS_URL = "https://api.tcgdex.net/v2/ja/sets"
SET_URL = "https://api.tcgdex.net/v2/ja/sets/{set_id}"
_UA = {"User-Agent": "Mozilla/5.0 (Splitdex)"}


def _fetch(url: str):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=30) as r:
            return json.load(r)
    except Exception:
        return None


def _normalize(number: str) -> str:
    return str(number).lstrip("0") or "0"


def main() -> None:
    init_db()
    connection = sqlite3.connect(str(DB_DIR / "splitdex.sqlite3"))

    sets = _fetch(SETS_URL) or []
    print(f"{len(sets)} sets japonais à parcourir…", flush=True)

    total = 0
    for index, summary in enumerate(sets, 1):
        payload = _fetch(SET_URL.format(set_id=summary["id"]))
        if not payload:
            continue
        # Le total OFFICIEL exclut les secrètes : c'est le dénominateur imprimé
        # sur la carte ("65/62"), pas le nombre réel de cartes du set.
        printed_total = (payload.get("cardCount") or {}).get("official")
        set_name = payload.get("name") or summary["id"]

        rows = [
            (
                card["id"], payload["id"], set_name, printed_total,
                _normalize(card["localId"]), card.get("name") or "", card.get("image"),
            )
            for card in payload.get("cards", [])
            if card.get("name")
        ]
        connection.executemany(
            """INSERT INTO japanese_cards
                   (id, set_id, set_name, printed_total, number, name, image_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   set_id=excluded.set_id, set_name=excluded.set_name,
                   printed_total=excluded.printed_total, number=excluded.number,
                   name=excluded.name, image_url=excluded.image_url""",
            rows,
        )
        connection.commit()
        total += len(rows)
        if index % 25 == 0:
            print(f"  {index}/{len(sets)} sets — {total} cartes", flush=True)

    count = connection.execute("SELECT COUNT(*) FROM japanese_cards").fetchone()[0]
    print(f"\nCatalogue japonais : {count} cartes en base.")


if __name__ == "__main__":
    main()
