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

import cv2
import numpy as np
import pytesseract
from PIL import Image

from app.core.language_detector import ocr_text

# "170/165", "23 / 102"... — le format quasi universel des cartes modernes.
# Les formats promo/spéciaux (ex: "SWSH233", "TG04") ne sont pas capturés ici
# et retombent sur le matching d'image, plus adapté à ces cas rares.
NUMBER_PATTERN = re.compile(r"(\d{1,4})\s*/\s*(\d{1,4})")

# Un numéro de carte plausible reste dans cette fourchette — évite de
# confondre avec un total de PV ou des dégâts d'attaque qui suivraient par
# coïncidence ce même motif "X/Y" sur une carte mal cadrée.
MAX_PLAUSIBLE_NUMBER = 2000


# Fenêtres où le numéro est imprimé, en fractions (y0, y1, x0, x1) de la carte :
# bas-gauche sur les cartes modernes, bas-droite sur les plus anciennes.
_NUMBER_WINDOWS = (
    (0.91, 0.99, 0.10, 0.40),
    (0.90, 1.00, 0.55, 0.95),
)
_FOCUS_WIDTH = 1200  # le numéro est minuscule : on l'agrandit franchement


def detect_card_number_focused(card_bgr: np.ndarray) -> tuple[str, str] | None:
    """Passe OCR CIBLÉE sur la zone du numéro, en dernier recours.

    Le numéro est imprimé en tout petit, souvent en blanc sur un fond doré ou
    holographique : les passes OCR globales (`ocr_text`) le noient dans le
    reste de la carte et ne le rendent quasiment jamais. Zoomer sur la bande du
    bas suffit à le lire (mesuré : "066/217" illisible globalement, lu
    correctement ici — la carte était identifiée sur la mauvaise extension).

    `card_bgr` doit inclure le bord bas de la carte : les boîtes de détection
    serrent souvent trop et rognent cette ligne (voir le paramètre `margin`
    d'`extract_card_native`)."""
    if card_bgr is None or card_bgr.size == 0:
        return None
    height, width = card_bgr.shape[:2]
    for y0, y1, x0, x1 in _NUMBER_WINDOWS:
        strip = card_bgr[int(height * y0) : int(height * y1), int(width * x0) : int(width * x1)]
        if strip.size == 0 or strip.shape[1] < 8:
            continue
        scaled = cv2.resize(
            strip,
            (_FOCUS_WIDTH, max(1, int(_FOCUS_WIDTH * strip.shape[0] / strip.shape[1]))),
            interpolation=cv2.INTER_CUBIC,
        )
        gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
        gray = cv2.addWeighted(gray, 1.7, cv2.GaussianBlur(gray, (0, 0), 3), -0.7, 0)
        try:
            # `--psm 11` (texte épars) : la bande contient aussi l'illustrateur
            # et le code de langue, une segmentation en bloc échoue.
            text = pytesseract.image_to_string(Image.fromarray(gray), config="--psm 11")
        except Exception:
            continue
        found = _first_plausible(text)
        if found:
            return found
    return None


def _first_plausible(text: str) -> tuple[str, str] | None:
    for number, total in NUMBER_PATTERN.findall(text or ""):
        if 1 <= int(number) <= MAX_PLAUSIBLE_NUMBER and 1 <= int(total) <= MAX_PLAUSIBLE_NUMBER:
            return str(int(number)), str(int(total))
    return None


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
