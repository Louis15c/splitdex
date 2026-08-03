"""Retrouve l'équivalent JAPONAIS d'une carte identifiée dans le catalogue
international, pour annoncer la référence réellement imprimée sur la carte.

Une carte japonaise porte un autre numéro et une autre extension : la Posipi
référencée "193/182 Faille Paradoxe" côté international est "65/62
レイジングサーフ" au Japon. L'acheteur cherche cette référence-là.

Aucun identifiant ne relie les deux catalogues. En revanche **l'illustration est
la même** : mesuré sur de vraies cartes, la distance de pHash entre les deux
éditions est de 6 à 10, contre 40 pour deux cartes sans rapport — l'écart est
donc franc. On combine deux critères indépendants :

1. l'ESPÈCE, via son nom japonais (`pokemon_names_jp`), qui réduit le catalogue
   à une poignée de candidats ;
2. l'ILLUSTRATION, qui tranche entre ces candidats.

Les visuels japonais ne sont téléchargés qu'à ce moment (quelques-uns par carte
scannée) et leur empreinte est mémorisée : rapatrier les 8 000 images du
catalogue serait long et inutile à 99%.
"""

import sqlite3
import urllib.request

import cv2
import numpy as np

from app.core.config import DB_DIR, REFERENCE_THUMBNAILS_DIR
from app.core.phash import compute_phash, hamming_distance
from app.core.pokemon_names_jp import POKEMON_NAME_JP

# Distance pHash maximale pour accepter un appariement. Mesuré : 6 et 10 sur des
# paires vraies, 40 sur une paire sans rapport — 16 laisse de la marge des deux
# côtés sans jamais rapprocher deux illustrations différentes.
MAX_PHASH_DISTANCE = 16
# Au-delà, la recherche par nom a mal ciblé : inutile de télécharger davantage.
MAX_CANDIDATES = 40
_UA = {"User-Agent": "Mozilla/5.0 (Splitdex)"}

# Nom usuel des extensions japonaises dans les annonces (celui qu'emploient
# vendeurs et acheteurs, ex. "raging surf"). TCGdex ne publie que le nom japonais
# (レイジングサーフ) et il n'existe pas de nom officiel français ; ces noms
# proviennent des sources de référence du TCG japonais (PokeGuardian, TCG
# Republic, Bulbapedia).
#
# À noter : on se fie au CODE de set, pas au nom renvoyé par TCGdex — celui-ci
# est parfois faux (il annonce "レイジングサーフ" pour SV4a, dont les cartes sont
# pourtant bien celles de Shiny Treasure ex).
#
# Un set absent de la table est annoncé par son code (ex. "SVLN"), factuel et
# jamais inventé. Compléter au fil des sets rencontrés.
JAPANESE_SET_NAMES = {
    # Écarlate et Violet
    "SV1S": "scarlet ex",
    "SV1V": "violet ex",
    "SV1a": "triplet beat",
    "SV2P": "snow hazard",
    "SV2D": "clay burst",
    "SV2a": "pokemon card 151",
    "SV3": "ruler of the black flame",
    "SV3a": "raging surf",
    "SV4K": "ancient roar",
    "SV4M": "future flash",
    "SV4a": "shiny treasure ex",
    "SV5K": "wild force",
    "SV5a": "crimson haze",
    "SV6": "mask of change",
    "SV7": "stellar miracle",
    "SV7a": "paradise dragona",
    "SV8": "super electric breaker",
    "SV8a": "terastal festival ex",
    "SV9": "battle partners",
    "SV9a": "hot air arena",
    "SV10": "glory of team rocket",
    "SV11B": "black bolt",
    "SV11W": "white flare",
    # Méga-Évolution
    "M1S": "mega symphonia",
    "M1L": "mega brave",
    "M2": "inferno X",
    "M2a": "mega dream ex",
    "M3": "nihil zero",
    "M4": "ninja spinner",
    "M5": "abyss eye",
}


def japanese_set_label(set_id: str) -> str:
    return JAPANESE_SET_NAMES.get(set_id, set_id)


def _species_japanese_name(card_name_en: str | None) -> str | None:
    """Nom japonais de l'espèce portée par un nom de carte ("Garchomp ex" ->
    ガブリアス) : on retient le mot le plus long qui est une espèce connue."""
    import re

    best = None
    for token in re.split(r"[^A-Za-z]+", card_name_en or ""):
        japanese = POKEMON_NAME_JP.get(token)
        if japanese and (best is None or len(token) > len(best[0])):
            best = (token, japanese)
    return best[1] if best else None


def _download_phash(image_url: str) -> str | None:
    try:
        request = urllib.request.Request(f"{image_url}/high.webp", headers=_UA)
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read()
    except Exception:
        return None
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    return compute_phash(image) if image is not None else None


def find_japanese_equivalent(card_id: str, card_name_en: str | None) -> dict | None:
    """Retourne {id, number, printed_total, set_id, set_name} de la carte
    japonaise correspondante, ou None. Le résultat est mémorisé sur la carte
    internationale (`reference_cards.jp_card_id`) pour n'être cherché qu'une
    fois — y compris l'échec, pour ne pas retenter à chaque affichage."""
    connection = sqlite3.connect(str(DB_DIR / "splitdex.sqlite3"))
    connection.row_factory = sqlite3.Row
    try:
        cached = connection.execute(
            "SELECT jp_card_id FROM reference_cards WHERE id = ?", (card_id,)
        ).fetchone()
        if cached is not None and cached["jp_card_id"] is not None:
            if not cached["jp_card_id"]:
                return None  # déjà cherché, sans succès
            return _load(connection, cached["jp_card_id"])

        found = _resolve(connection, card_id, card_name_en)
        connection.execute(
            "UPDATE reference_cards SET jp_card_id = ? WHERE id = ?",
            (found["id"] if found else "", card_id),
        )
        connection.commit()
        return found
    finally:
        connection.close()


def _load(connection: sqlite3.Connection, japanese_id: str) -> dict | None:
    row = connection.execute(
        "SELECT id, number, printed_total, set_id, set_name FROM japanese_cards WHERE id = ?",
        (japanese_id,),
    ).fetchone()
    return dict(row) if row else None


def _resolve(connection: sqlite3.Connection, card_id: str, card_name_en: str | None) -> dict | None:
    japanese_name = _species_japanese_name(card_name_en)
    if not japanese_name:
        return None

    reference = cv2.imread(str(REFERENCE_THUMBNAILS_DIR / f"{card_id}.jpg"))
    if reference is None:
        return None
    reference_hash = compute_phash(reference)

    candidates = connection.execute(
        "SELECT id, number, printed_total, set_id, set_name, image_url, phash "
        "FROM japanese_cards WHERE name LIKE ? LIMIT ?",
        (f"%{japanese_name}%", MAX_CANDIDATES),
    ).fetchall()

    best, best_distance = None, None
    for candidate in candidates:
        candidate_hash = candidate["phash"]
        if not candidate_hash:
            if not candidate["image_url"]:
                continue
            candidate_hash = _download_phash(candidate["image_url"])
            if not candidate_hash:
                continue
            connection.execute(
                "UPDATE japanese_cards SET phash = ? WHERE id = ?", (candidate_hash, candidate["id"])
            )
            connection.commit()
        distance = hamming_distance(reference_hash, candidate_hash)
        if best_distance is None or distance < best_distance:
            best, best_distance = candidate, distance

    if best is None or best_distance > MAX_PHASH_DISTANCE:
        return None
    return {key: best[key] for key in ("id", "number", "printed_total", "set_id", "set_name")}
