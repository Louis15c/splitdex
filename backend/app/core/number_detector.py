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

from app.core.language_detector import ocr_text, run_tesseract

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


def _text_rows(gray: np.ndarray, min_height: int = 6) -> list[tuple[int, int]]:
    """Lignes de texte de la bande, par projection horizontale du gradient.

    Un fond — uni, dégradé ou holographique — présente peu de bords ; le texte
    en présente beaucoup. Les intervalles où cette densité dépasse la moyenne
    délimitent donc les lignes."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    profile = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel).mean(axis=1)
    threshold = profile.mean() + 0.3 * profile.std()
    rows: list[tuple[int, int]] = []
    start = None
    for y, value in enumerate(profile):
        if value > threshold and start is None:
            start = y
        elif value <= threshold and start is not None:
            if y - start >= min_height:
                rows.append((start, y))
            start = None
    if start is not None and len(profile) - start >= min_height:
        rows.append((start, len(profile)))
    return rows


def _focused_ocr(image: np.ndarray) -> np.ndarray:
    """Agrandit franchement et renforce les contours : le numéro est minuscule."""
    height, width = image.shape[:2]
    scaled = cv2.resize(
        image,
        (_FOCUS_WIDTH, max(1, int(_FOCUS_WIDTH * height / width))),
        interpolation=cv2.INTER_CUBIC,
    )
    gray = scaled if scaled.ndim == 2 else cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
    return cv2.addWeighted(gray, 1.7, cv2.GaussianBlur(gray, (0, 0), 3), -0.7, 0)


# Au-delà, on renonce : les lectures réussies aboutissent en 4 appels au plus
# (mesuré sur photo 4K), tandis qu'un échec pouvait en enchaîner 34 et coûter
# 3,5s. Ce plafond ramène le pire cas sous la seconde sans rien perdre.
_MAX_OCR_ATTEMPTS = 10


def detect_card_number_focused(card_bgr: np.ndarray) -> tuple[str, str] | None:
    """Passe OCR CIBLÉE sur la zone du numéro, en dernier recours.

    Ce ne sont ni la netteté ni la taille qui sont en cause. Sur une photo 4K,
    le numéro est en chiffres NOIRS (5 de gris) sur un aplat uniforme (71-80),
    sans illustration derrière — et la carte entière poussée à x4, chiffres
    hauts de 188px, rend toujours "<2" et "G".

    La cause est le VOISINAGE. Le numéro est encadré de pictogrammes (symbole
    d'extension, lettre encadrée, étoile de rareté). Tesseract regroupe les
    glyphes en mots d'après leur espacement, agglomère ces pictogrammes avec
    les chiffres, et son modèle ne produit rien de sensé pour ce mélange. Il
    voit pourtant bien une zone de texte au bon endroit : il la rend "y", "Q"
    ou "7,6" selon le mode. La ligne de copyright juste en dessous passe très
    bien, elle, car aucun pictogramme ne la jouxte.

    Démonstration, même ligne et même agrandissement :
        avec les pictogrammes  -> "cS?"
        sans les pictogrammes  -> "068/798 *"

    D'où la méthode : isoler les lignes de texte, puis découper chaque ligne en
    moitiés pour séparer les chiffres des pictogrammes. Le découpage horizontal
    n'est pas un rattrapage, c'est le mécanisme même — la lecture réussie vient
    du morceau qui laisse les symboles dehors. Mesuré : 2 numéros lus sur 9
    auparavant, 6 sur 9 ensuite, pour ~0,3s par carte quand elle aboutit.

    `card_bgr` doit inclure le bord bas de la carte : les boîtes de détection
    serrent souvent trop et rognent cette ligne (voir le paramètre `margin`
    d'`extract_card_native`)."""
    if card_bgr is None or card_bgr.size == 0:
        return None
    height, width = card_bgr.shape[:2]
    attempts = 0
    for y0, y1, x0, x1 in _NUMBER_WINDOWS:
        strip = card_bgr[int(height * y0) : int(height * y1), int(width * x0) : int(width * x1)]
        if strip.size == 0 or strip.shape[1] < 8:
            continue

        # `--psm 11` (texte épars) sur la bande entière : le moins cher, et il
        # suffit quand le numéro est bien détaché de son fond.
        attempts += 1
        found = _first_plausible(run_tesseract(_focused_ocr(strip), psm=11))
        if found:
            return found

        gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
        for row_start, row_end in _text_rows(gray):
            if attempts >= _MAX_OCR_ATTEMPTS:
                return None
            padding = max(1, (row_end - row_start) // 6)
            line = strip[
                max(0, row_start - padding) : min(strip.shape[0], row_end + padding), :
            ]
            if line.shape[0] < 6:
                continue
            # `--psm 7` : une ligne unique, ce qu'on vient précisément d'isoler.
            attempts += 1
            found = _first_plausible(run_tesseract(_focused_ocr(line), psm=7))
            if found:
                return found

            # La ligne porte aussi symboles et illustrateur : les tiers en
            # écartent l'essentiel sans présumer de quel côté est le numéro.
            line_width = line.shape[1]
            for offset in (0.0, 0.25, 0.5):
                if attempts >= _MAX_OCR_ATTEMPTS:
                    return None
                piece = line[:, int(line_width * offset) : int(line_width * min(1.0, offset + 0.5))]
                if piece.shape[1] < 10:
                    continue
                attempts += 1
                found = _first_plausible(run_tesseract(_focused_ocr(piece), psm=7))
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
