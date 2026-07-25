"""Ajoute au cache de référence les promos SV Black Star (`svp`) absentes.

Contexte : pokemontcg.io ne référence pas les promos SV récentes (2025), et
TCGdex a bien leurs métadonnées mais **sans image** (`image: null`) — donc le
`sync_cards` habituel ne peut pas les récupérer et l'identification par image
est impossible. Les visuels existent en revanche sur LimitlessTCG, avec des URL
prévisibles par numéro. Ce script comble ce trou précis :

1. diffe le set `svp` local contre TCGdex (numéros normalisés) ;
2. télécharge l'image de chaque carte manquante depuis LimitlessTCG (celles
   qui y sont — certaines n'y sont pas encore) ;
3. crée la vignette (245x342, comme le reste du cache), calcule le pHash et
   insère la ligne dans `reference_cards`.

Idempotent : relançable, les cartes déjà en base sont sautées.

APRÈS ce script, lancer l'index d'embeddings (resumable, ne calcule que les
nouvelles vignettes) :
    python -m app.scripts.build_card_embeddings

Usage : python -m app.scripts.scrape_svp_promos
"""

import datetime
import json
import sqlite3
import urllib.request

import cv2
import numpy as np

from app.core.config import DB_DIR, REFERENCE_THUMBNAILS_DIR
from app.core.phash import compute_phash

SET_ID = "svp"
SET_NAME = "Scarlet & Violet Black Star Promos"
SERIES = "Scarlet & Violet"
PRINTED_TOTAL = 215
TCGDEX_SET_URL = "https://api.tcgdex.net/v2/en/sets/svp"
# LimitlessTCG : visuel grand format, nommé par numéro de carte.
LIMITLESS_URL = "https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/tpci/SVP/SVP_{num}_R_EN_LG.png"
THUMB_SIZE = (245, 342)  # (largeur, hauteur), aligné sur les vignettes existantes
_UA = {"User-Agent": "Mozilla/5.0 (Splitdex)"}


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=30) as r:
        return json.load(r)


def _download(url: str) -> bytes | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=30) as r:
            return r.read()
    except Exception:
        return None


def _norm(number: str) -> str:
    return str(number).lstrip("0") or "0"


def main() -> None:
    con = sqlite3.connect(str(DB_DIR / "splitdex.sqlite3"))
    have = {_norm(r[0]) for r in con.execute(
        "SELECT number FROM reference_cards WHERE set_id = ?", (SET_ID,)
    )}

    cards = _fetch_json(TCGDEX_SET_URL).get("cards", [])
    missing = [c for c in cards if _norm(c["localId"]) not in have]
    print(f"{SET_ID} : {len(cards)} cartes TCGdex, {len(have)} en base, {len(missing)} manquantes.")

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    added, no_image = [], []
    for card in missing:
        local_id = card["localId"]
        number = _norm(local_id)
        card_id = f"{SET_ID}-{number}"
        url = LIMITLESS_URL.format(num=local_id)
        data = _download(url)
        if data is None:
            no_image.append(card_id)
            continue
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            no_image.append(card_id)
            continue
        thumb = cv2.resize(image, THUMB_SIZE, interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(REFERENCE_THUMBNAILS_DIR / f"{card_id}.jpg"), thumb, [cv2.IMWRITE_JPEG_QUALITY, 90])
        con.execute(
            """INSERT OR REPLACE INTO reference_cards
               (id, name, set_id, set_name, number, printed_total, rarity,
                small_image_url, large_image_url, phash, synced_at, series)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (card_id, card.get("name"), SET_ID, SET_NAME, number, PRINTED_TOTAL, "Promo",
             url, url, compute_phash(thumb), now, SERIES),
        )
        added.append(card_id)

    con.commit()
    print(f"Ajoutées : {len(added)} -> {added}")
    if no_image:
        print(f"Sans image disponible (ignorées) : {len(no_image)} -> {no_image}")
    if added:
        print("\nÉtape suivante : python -m app.scripts.build_card_embeddings")


if __name__ == "__main__":
    main()
