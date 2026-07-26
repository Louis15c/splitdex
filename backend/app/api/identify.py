import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import cv2
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.card_detector import extract_card_native
from app.core.card_identifier import MatchCandidate, load_reference_index
from app.core.config import CROPS_DIR, UPLOADS_DIR
from app.core.db import db_cursor, get_connection
from app.core.language_detector import detect_language, ocr_text
from app.core.number_detector import detect_card_number, detect_card_number_focused
from app.core.card_translations import translate_set_name
from app.core.pokemon_names_fr import translate_card_name_to_fr
from app.core.validation import validate_photo_id

router = APIRouter(prefix="/api/photos", tags=["identify"])

TOP_K = 3
CONFIDENT_ORB_SCORE = 15  # en dessous, le match est jugé peu fiable (cf. card_identifier.py)
# Crops traités en parallèle : l'OCR (Tesseract, sous-processus mono-thread,
# voir OMP_THREAD_LIMIT dans language_detector.py) et l'ORB (OpenCV) libèrent
# le GIL, des threads suffisent. Adapté au matériel : cœurs - 1 (on garde un
# cœur pour le serveur), borné à [2, 6] — au-delà de 6, l'OCR sature le débit
# mémoire avant les cœurs et les gains s'écrasent. Donne 3 sur la VM (4
# cœurs) et 6 sur un MacBook M1 (8 cœurs), sans réglage manuel.
IDENTIFY_WORKERS = max(2, min(6, (os.cpu_count() or 4) - 1))

# Largeur des crops sauvegardés (cf. card_detector.OUTPUT_WIDTH) : en dessous,
# re-warper depuis la photo d'origine n'apporte AUCUN pixel supplémentaire.
SAVED_CROP_WIDTH = 480


def _ocr_source(crop: dict, saved_image, original_photo):
    """Meilleure source OCR pour ce crop : la photo d'origine re-warpée quand
    la carte y occupe plus de pixels que le crop sauvegardé (photo de téléphone
    haute résolution : le crop perd du détail au rééchantillonnage à 480px +
    JPEG), sinon le crop sauvegardé lui-même.

    Re-warper une carte plus PETITE que 480px ne fait qu'agrandir la même zone
    par interpolation, sans gain de détail — et l'image lissée obtenue se lit en
    pratique moins bien que le crop (constaté : nom "Mystherbe" lu sur le crop,
    illisible sur l'extraction native d'une photo 800x600, d'où une carte
    identifiée à tort faute d'indice de nom)."""
    corners = crop.get("corners")
    if original_photo is None or not corners:
        return saved_image
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    native_size = min(max(xs) - min(xs), max(ys) - min(ys))
    if native_size <= SAVED_CROP_WIDTH:
        return saved_image
    try:
        return extract_card_native(original_photo, corners)
    except Exception:
        return saved_image


# Élargissement des coins pour la lecture du numéro : les boîtes détectées
# rognent souvent la dernière ligne de la carte, celle qui porte le numéro.
NUMBER_CROP_MARGIN = 1.06


def _focused_number(crop: dict, text: str, original_photo):
    """Numéro de carte lu par passe ciblée, uniquement quand l'OCR global n'en
    a trouvé aucun — le numéro désigne la carte exacte au sein d'un set, et son
    absence laissait choisir la mauvaise extension (constaté : Vikavolt
    066/217 identifié 53/142). Nécessite la photo d'origine, seule à contenir
    le bord bas rogné par la découpe."""
    if detect_card_number(None, text=text):
        return None  # déjà lisible dans l'OCR global, rien à refaire
    corners = crop.get("corners")
    if original_photo is None or not corners:
        return None
    try:
        card = extract_card_native(original_photo, corners, margin=NUMBER_CROP_MARGIN)
    except Exception:
        return None
    return detect_card_number_focused(card)


def _crops_dir(photo_id: str):
    return CROPS_DIR / photo_id


def _crops_meta_path(photo_id: str):
    return _crops_dir(photo_id) / "meta.json"


def _serialize_candidate(candidate: MatchCandidate) -> dict:
    return {
        "card_id": candidate.card_id,
        # Nom affiché en français (public francophone) ; le card_id reste la
        # référence technique.
        "name": translate_card_name_to_fr(candidate.name),
        # Set en français ; set_id dérivé du card_id ("{set_id}-{numéro}").
        "set_name": translate_set_name(candidate.set_name, candidate.card_id.rsplit("-", 1)[0]),
        "number": candidate.number,
        "rarity": candidate.rarity,
        "image_url": f"/reference-images/{candidate.card_id}.jpg",
        "phash_distance": candidate.phash_distance,
        "orb_score": candidate.orb_score,
        "matched_by": candidate.matched_by,
    }


# Vote majoritaire : au moins 2 cartes déterminées, et une majorité
# ÉCRASANTE parmi elles pour remplir les indéterminées. À 80%, une photo
# homogène (toutes françaises) remplit tout, un classeur presque homogène
# (8 françaises + 1 japonaise = 89%) aussi — mais une photo franchement
# mixte (10 FR + 5 EN mesurée : 67%) ne remplit rien : une carte anglaise
# illisible y serait étiquetée "Français", et une langue FAUSSE est pire
# qu'une langue absente (le prix serait cherché dans le mauvais catalogue,
# sans que rien ne le signale).
MIN_MAJORITY_VOTES = 2
MIN_MAJORITY_FRACTION = 0.8


def _fill_language_by_majority(identified: list) -> None:
    """Les cartes d'une même photo sont presque toujours imprimées dans la
    même langue : les cartes dont la langue a été déterminée (vocabulaire du
    texte d'attaque ou nom d'espèce) votent pour celles restées indéterminées
    (texte illisible sur les photos à faible résolution). Ne touche JAMAIS à
    une carte déjà déterminée — une photo mixte (classeur FR + quelques
    japonaises) garde ses déterminations individuelles."""
    from collections import Counter

    determinate = [
        result.language for _, result in identified if result is not None and result.language
    ]
    if not determinate:
        return
    (majority_language, votes), = Counter(determinate).most_common(1)
    if votes < MIN_MAJORITY_VOTES or votes < MIN_MAJORITY_FRACTION * len(determinate):
        return
    for _, result in identified:
        if result is not None and result.language is None:
            result.language = majority_language


@router.post("/{photo_id}/identify")
def identify_cards(photo_id: str):
    validate_photo_id(photo_id)
    meta_path = _crops_meta_path(photo_id)
    if not meta_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Aucun crop trouvé pour cette photo. Lance d'abord la découpe des cartes.",
        )

    crops = json.loads(meta_path.read_text())
    if not crops:
        return []

    index = load_reference_index()
    if index.is_empty():
        raise HTTPException(
            status_code=503,
            detail=(
                "Le cache local de cartes de référence est vide. Lance d'abord la synchronisation "
                "pokemontcg.io : backend/app/scripts/sync_cards.py"
            ),
        )

    photo_crop_dir = _crops_dir(photo_id)
    results = []

    # Photo originale (si encore présente) : source OCR de bien meilleure
    # qualité que les crops sauvegardés (rééchantillonnés à 480px puis
    # recompressés JPEG) — décisif quand une carte ne fait que ~300px dans la
    # photo. Les corners de meta.json permettent de re-warper à la volée.
    original_photo = None
    for candidate in UPLOADS_DIR.glob(f"{photo_id}.*"):
        if candidate.is_file():
            original_photo = cv2.imread(str(candidate))
            break

    def _identify_crop(crop):
        """OCR unique par crop, partagé entre la détection de langue et les
        indices numéro/nom de `identify` — l'OCR est l'étape la plus lente
        (~3s par passe), le relancer par détecteur triplait le temps total."""
        crop_path = photo_crop_dir / crop["filename"]
        image = cv2.imread(str(crop_path))
        if image is None:
            return crop, None
        ocr_source = _ocr_source(crop, image, original_photo)
        text = ocr_text(ocr_source)
        language = detect_language(ocr_source, text=text)
        number_hint = _focused_number(crop, text, original_photo)
        return crop, index.identify(
            image, top_k=TOP_K, language=language, text=text, number_hint=number_hint
        )

    with ThreadPoolExecutor(max_workers=IDENTIFY_WORKERS) as executor:
        identified = list(executor.map(_identify_crop, crops))

    _fill_language_by_majority(identified)

    with db_cursor() as cursor:
        for crop, result in identified:
            if result is None:
                continue

            candidates, language = result.candidates, result.language
            best = candidates[0] if candidates else None
            confident = best is not None and best.orb_score >= CONFIDENT_ORB_SCORE

            serialized_candidates = [_serialize_candidate(c) for c in candidates]
            result = {
                "crop_filename": crop["filename"],
                "crop_index": crop["index"],
                "best_match": serialized_candidates[0] if serialized_candidates else None,
                "confident": confident,
                "candidates": serialized_candidates,
                "language": language,
            }
            results.append(result)

            cursor.execute(
                """
                INSERT INTO identifications
                    (photo_id, crop_filename, card_id, orb_score, candidates_json, language, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(photo_id, crop_filename) DO UPDATE SET
                    card_id=excluded.card_id, orb_score=excluded.orb_score,
                    candidates_json=excluded.candidates_json, language=excluded.language,
                    created_at=excluded.created_at
                """,
                (
                    photo_id,
                    crop["filename"],
                    best.card_id if best else None,
                    best.orb_score if best else None,
                    json.dumps(serialized_candidates),
                    language,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    return results


_INSERT_IDENTIFICATION_SQL = """
    INSERT INTO identifications
        (photo_id, crop_filename, card_id, orb_score, candidates_json, language, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(photo_id, crop_filename) DO UPDATE SET
        card_id=excluded.card_id, orb_score=excluded.orb_score,
        candidates_json=excluded.candidates_json, language=excluded.language,
        created_at=excluded.created_at
"""


def _identification_payload(crop: dict, result) -> dict:
    """Forme JSON d'une carte identifiée (même contenu que /identify)."""
    if result is None:
        return {
            "type": "card", "crop_filename": crop["filename"], "crop_index": crop["index"],
            "best_match": None, "confident": False, "candidates": [], "language": None,
        }
    candidates = [_serialize_candidate(c) for c in result.candidates]
    best = result.candidates[0] if result.candidates else None
    return {
        "type": "card",
        "crop_filename": crop["filename"],
        "crop_index": crop["index"],
        "best_match": candidates[0] if candidates else None,
        "confident": best is not None and best.orb_score >= CONFIDENT_ORB_SCORE,
        "candidates": candidates,
        "language": result.language,
    }


def _write_identification(conn, photo_id: str, crop: dict, result) -> None:
    candidates = [_serialize_candidate(c) for c in result.candidates] if result else []
    best = result.candidates[0] if (result and result.candidates) else None
    conn.execute(
        _INSERT_IDENTIFICATION_SQL,
        (
            photo_id, crop["filename"],
            best.card_id if best else None,
            best.orb_score if best else None,
            json.dumps(candidates),
            result.language if result else None,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


@router.post("/{photo_id}/identify/stream")
def identify_cards_stream(photo_id: str):
    """Identifie les cartes en flux NDJSON : émet chaque carte dès qu'elle est
    prête (au lieu d'attendre toute la photo), puis, une fois tout identifié, un
    correctif de langue par vote majoritaire. Traitement et précision
    identiques à /identify — seule la restitution est progressive."""
    validate_photo_id(photo_id)
    meta_path = _crops_meta_path(photo_id)
    if not meta_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Aucun crop trouvé pour cette photo. Lance d'abord la découpe des cartes.",
        )
    crops = json.loads(meta_path.read_text())
    index = load_reference_index()
    if index.is_empty():
        raise HTTPException(
            status_code=503,
            detail=(
                "Le cache local de cartes de référence est vide. Lance d'abord la synchronisation "
                "pokemontcg.io : backend/app/scripts/sync_cards.py"
            ),
        )

    photo_crop_dir = _crops_dir(photo_id)
    original_photo = None
    for candidate in UPLOADS_DIR.glob(f"{photo_id}.*"):
        if candidate.is_file():
            original_photo = cv2.imread(str(candidate))
            break

    def _identify_crop(crop):
        crop_path = photo_crop_dir / crop["filename"]
        image = cv2.imread(str(crop_path))
        if image is None:
            return crop, None
        ocr_source = _ocr_source(crop, image, original_photo)
        text = ocr_text(ocr_source)
        language = detect_language(ocr_source, text=text)
        number_hint = _focused_number(crop, text, original_photo)
        return crop, index.identify(
            image, top_k=TOP_K, language=language, text=text, number_hint=number_hint
        )

    def generate():
        if not crops:
            return
        conn = get_connection()
        try:
            identified = []
            with ThreadPoolExecutor(max_workers=IDENTIFY_WORKERS) as executor:
                futures = [executor.submit(_identify_crop, crop) for crop in crops]
                for future in as_completed(futures):
                    crop, result = future.result()
                    identified.append((crop, result))
                    if result is not None:
                        _write_identification(conn, photo_id, crop, result)
                    yield json.dumps(_identification_payload(crop, result), ensure_ascii=False) + "\n"

            # Vote majoritaire : peut remplir des langues restées indéterminées.
            before = {id(result): (result.language if result else None) for _, result in identified}
            _fill_language_by_majority(identified)
            for crop, result in identified:
                if result is not None and result.language != before[id(result)]:
                    _write_identification(conn, photo_id, crop, result)
                    yield json.dumps(
                        {"type": "language", "crop_filename": crop["filename"], "language": result.language},
                        ensure_ascii=False,
                    ) + "\n"
        finally:
            conn.close()
        yield json.dumps({"type": "done"}, ensure_ascii=False) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.get("/{photo_id}/identify")
def get_identifications(photo_id: str):
    validate_photo_id(photo_id)
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT crop_filename, card_id, orb_score, candidates_json, language "
            "FROM identifications WHERE photo_id = ?",
            (photo_id,),
        )
        rows = cursor.fetchall()

    return [
        {
            "crop_filename": row["crop_filename"],
            "best_match": next(
                (c for c in json.loads(row["candidates_json"]) if c["card_id"] == row["card_id"]),
                None,
            ),
            "confident": row["orb_score"] is not None and row["orb_score"] >= CONFIDENT_ORB_SCORE,
            "candidates": json.loads(row["candidates_json"]),
            "language": row["language"],
        }
        for row in rows
    ]
