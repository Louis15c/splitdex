"""Extraction OCR du numéro imprimé sur une carte (ex: "170/165"), pour
identifier une carte directement par numéro plutôt que par comparaison
d'image sur tout le catalogue.

Le numéro imprimé est en chiffres arabes quelle que soit la langue
d'impression (contrairement au texte des attaques/mots-clés) — un signal
d'identification bien plus robuste multi-langue que le matching d'image pur,
tant que l'OCR arrive à le lire correctement sur la photo. Si Tesseract
n'est pas installé, ou si aucun numéro plausible n'est trouvé, retourne
`None` : l'appelant se rabat alors sur la comparaison d'image classique
(pHash + ORB) sur tout le catalogue.
"""

import re

import numpy as np

from app.core.language_detector import ocr_text

# "170/165", "23 / 102"... — le format quasi universel des cartes modernes.
# Les formats promo/spéciaux (ex: "SWSH233", "TG04") ne sont pas capturés ici
# et retombent sur le matching d'image, plus adapté à ces cas rares.
NUMBER_PATTERN = re.compile(r"(\d{1,4})\s*/\s*(\d{1,4})")

# Un numéro de carte plausible reste dans cette fourchette — évite de
# confondre avec un total de PV ou des dégâts d'attaque qui suivraient par
# coïncidence ce même motif "X/Y" sur une carte mal cadrée.
MAX_PLAUSIBLE_NUMBER = 2000


def detect_card_number(image_bgr: np.ndarray, text: str | None = None) -> tuple[str, str] | None:
    """Retourne (numéro, total) si trouvé avec confiance, sinon `None`.

    `text` : résultat d'`ocr_text` déjà calculé pour ce crop (voir
    `detect_language` — évite de relancer l'OCR, l'étape la plus lente).
    """
    if text is None:
        text = ocr_text(image_bgr)
    if not text:
        return None

    match = NUMBER_PATTERN.search(text)
    if not match:
        return None

    number, total = match.group(1), match.group(2)
    if not (1 <= int(number) <= MAX_PLAUSIBLE_NUMBER) or not (1 <= int(total) <= MAX_PLAUSIBLE_NUMBER):
        return None

    return number, total
