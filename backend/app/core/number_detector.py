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


# Deux dosages de renforcement. Ce n'est pas de la redondance : sur un numéro
# haut d'une vingtaine de pixels, le résultat bascule de l'un à l'autre. Mesuré
# sur une carte ère EX (Rayquaza 16/110, source de 162x26 px) — 1,7/-0,7 rend
# « 164110 », la barre oblique lue comme un 4, tandis que 1,8/-0,8 rend
# « 16/110 ». Élire l'un des deux reviendrait à régler un paramètre sur un seul
# échantillon.
#
# L'ORDRE compte, et coûte cher si on se trompe : tenter les deux dosages sur
# CHAQUE morceau consomme le budget deux fois plus vite, donc explore moitié
# moins de morceaux. Mesuré sur les 612 cartes de l'historique — 77 lectures
# dont 32 discordantes en 1,88s, contre 78 lectures dont 29 discordantes en
# 1,09s avec un seul dosage : approfondir coûtait 73% de temps pour aucune
# lecture de plus et davantage d'erreurs. On balaie donc TOUS les morceaux au
# premier dosage avant de recommencer au second.
_FOCUS_SHARPENING = (1.7, -0.7)
# Dosage de secours, tenté UNIQUEMENT sur un morceau qui a livré une suite de
# chiffres sans séparateur — signature d'un numéro présent dont la barre
# oblique a été perdue (mesuré : « 164110 » pour 16/110, le « / » lu comme un
# 4). Rattraper précisément ce cas coûte un appel de plus sur les seuls
# morceaux concernés, là où un second balayage complet doublait le temps de
# TOUTES les cartes pour aucune lecture de plus sur 612 (77 lectures en 1,88s
# contre 78 en 1,09s).
_FOCUS_SHARPENING_RESCUE = (1.8, -0.8)
_GLUED_DIGITS = re.compile(r"\d{4,7}")


def _focused_ocr(image: np.ndarray, sharpening: tuple[float, float] = _FOCUS_SHARPENING) -> np.ndarray:
    """Agrandit franchement et renforce les contours : le numéro est minuscule."""
    height, width = image.shape[:2]
    scaled = cv2.resize(
        image,
        (_FOCUS_WIDTH, max(1, int(_FOCUS_WIDTH * height / width))),
        interpolation=cv2.INTER_CUBIC,
    )
    gray = scaled if scaled.ndim == 2 else cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
    alpha, beta = sharpening
    return cv2.addWeighted(gray, alpha, cv2.GaussianBlur(gray, (0, 0), 3), beta, 0)





# Budget d'appels OCR PAR FENÊTRE, et non pour l'ensemble. Un budget global
# était consommé en entier par la première fenêtre explorée : sur les cartes
# ère EX, dont le numéro est en bas à DROITE, la fenêtre de gauche (vide, mais
# riche en texte : code de série, copyright) épuisait les 10 appels avant que
# la droite ne soit seulement tentée. Le numéro était lisible et lu — « 2/113 »
# sortait correctement au premier essai de la bonne fenêtre — mais on n'y
# arrivait jamais. Deux cartes identifiées dans la mauvaise extension pour
# cette seule raison.
#
# Les lectures réussies aboutissent en 4 appels au plus dans leur fenêtre ; le
# plafond borne donc chaque fenêtre sans jamais affamer la suivante.
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
    for y0, y1, x0, x1 in _NUMBER_WINDOWS:
        strip = card_bgr[int(height * y0) : int(height * y1), int(width * x0) : int(width * x1)]
        if strip.size == 0 or strip.shape[1] < 8:
            continue

        # `--psm 11` (texte épars) sur la bande entière : le moins cher, et il
        # suffit quand le numéro est bien détaché de son fond.
        found = _first_plausible(run_tesseract(_focused_ocr(strip), psm=11))
        if found:
            return found

        rows = _text_rows(cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY))
        attempts = 0  # budget propre à cette fenêtre
        for row_start, row_end in rows:
            if attempts >= _MAX_OCR_ATTEMPTS:
                break
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
                    break
                piece = line[:, int(line_width * offset) : int(line_width * min(1.0, offset + 0.5))]
                if piece.shape[1] < 10:
                    continue
                attempts += 1
                text = run_tesseract(_focused_ocr(piece), psm=7)
                found = _first_plausible(text)
                if found:
                    return found
                # Chiffres collés sans séparateur : le numéro est là, seule la
                # barre oblique a sauté. Un seul dosage de secours sur CE
                # morceau suffit à la retrouver.
                if _GLUED_DIGITS.search(text or ""):
                    attempts += 1
                    found = _first_plausible(
                        run_tesseract(_focused_ocr(piece, _FOCUS_SHARPENING_RESCUE), psm=7)
                    )
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
