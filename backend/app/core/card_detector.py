"""Détection et découpe automatique de cartes à jouer sur une photo.

Depuis l'entraînement d'un modèle YOLO dédié (voir `card_detector_yolo.py`
et `backend/app/scripts/train_card_yolo.py`), ce module par contours OpenCV
n'est plus que le **filet de secours** utilisé si le modèle YOLO n'est pas
disponible (pas encore entraîné) — `detect_cards()` essaie YOLO en premier.
En usage réel, YOLO s'est montré bien plus robuste sur des fonds texturés ou
des cartes qui se touchent, deux cas qui faisaient concrètement échouer
l'approche ci-dessous. Ce qui suit ne documente donc que le pipeline de
secours.

Hypothèse de travail : les cartes sont posées à plat sur un fond contrasté
(couleur unie, différente des cartes), photographiées depuis le dessus.

Approche : détection de contours (Canny + fermeture morphologique), filtrage
par aire et ratio d'aspect proche du format standard d'une carte à jouer
(63x88mm), puis correction de perspective vers une image rectangulaire de
taille fixe. Un fallback par ligne de partage des eaux (watershed) tente de
séparer les contours qui fusionnent plusieurs cartes se chevauchant
légèrement (angle, coin qui recouvre une autre carte).

Limite connue (chevauchement) : deux cartes parfaitement alignées et
strictement adjacentes (bord à bord, sans chevauchement ni angle) ne créent
aucune concavité dans le contour extérieur fusionné — aucune méthode
purement géométrique sur le seul contour ne peut alors les séparer sans
indice supplémentaire (couleur, texture). En pratique, de vraies photos de
cartes physiques ont presque toujours une ombre ou un liseré visible à la
jointure, ce qui contourne ce cas.

Limite connue (fond texturé) : `CONTOUR_PRESETS` essaie plusieurs réglages
de flou/seuils Canny/fermeture avant d'abandonner, ce qui aide sur des fonds
légèrement texturés (bois, tissu à motif discret). Mais testé en pratique
sur un vrai tissu à motif fortement contrasté (diamants noir/beige d'une
intensité comparable aux bords des cartes), même ces réglages de secours
produisent des découpes fausses (grand pan de fond + carte partielle) plutôt
que d'échouer proprement — aucun réglage géométrique ne peut fiablement
distinguer "bord de carte" de "bord du motif" quand les deux ont une force
de contour similaire. Pour un fond à ce point texturé, la seule solution
fiable est d'utiliser une surface unie (feuille de papier de couleur, tapis
neutre) plutôt que d'attendre que l'algorithme s'adapte à tout.
"""

from dataclasses import dataclass

import cv2
import numpy as np

CARD_ASPECT_RATIO = 63 / 88  # largeur / hauteur, format standard carte à jouer
OUTPUT_WIDTH = 480
OUTPUT_HEIGHT = round(OUTPUT_WIDTH / CARD_ASPECT_RATIO)

MAX_PROCESSING_DIM = 1600  # sous-échantillonnage pour accélérer la détection
MIN_AREA_RATIO = 0.004  # une carte fait au moins ~0.4% de la surface de la photo
MAX_AREA_RATIO = 0.35  # aire max plausible pour une carte isolée
MAX_MERGE_AREA_RATIO = 0.65  # aire max plausible pour un amas de quelques cartes
ASPECT_RATIO_TOLERANCE = 0.18
MERGED_AREA_FACTOR = 1.5  # aire > 1.5x la taille typique estimée = probable amas
MIN_TYPICAL_AREA_FACTOR = 0.5  # aire < 50% de la taille typique = probable fragment parasite

# Plusieurs réglages de détection de contours, essayés dans l'ordre : le
# premier est celui qui marche bien sur un fond uni contrasté (cas nominal).
# Les suivants sont des filets de sécurité pour des fonds légèrement texturés
# (bois, tissu à motif discret...) où un flou plus fort et moins de fermeture
# morphologique limitent le risque que la texture du fond fusionne avec les
# bords des cartes en un seul gros contour. Sur un fond très fortement
# texturé (motif contrasté façon tissu à imprimé marqué), aucun réglage
# purement géométrique ne peut garantir une séparation fiable — préférer un
# fond uni reste la façon la plus fiable d'obtenir une détection propre.
CONTOUR_PRESETS = [
    {"blur": 5, "canny_low": 30, "canny_high": 100, "close_kernel": 5, "close_iterations": 2},
    {"blur": 9, "canny_low": 50, "canny_high": 150, "close_kernel": 3, "close_iterations": 1},
    {"blur": 5, "canny_low": "auto", "canny_high": "auto", "close_kernel": 5, "close_iterations": 2},
]


@dataclass
class DetectedCard:
    index: int
    corners: list  # 4 points (x, y) dans le repère de l'image originale
    image: np.ndarray  # crop redressé (BGR)
    preset_index: int  # 0 = réglage nominal (fond uni) ; > 0 = filet de sécurité, à vérifier


# Format d'une carte : portrait ~0,72, paysage ~1,40 (cartes BREAK/TURBO).
_CARD_RATIO_BANDS = ((0.60, 0.85), (1.18, 1.67))
# En dessous de cette fraction de l'image, la plus grosse "carte" détectée est
# jugée être un motif interne parasite, pas la carte (voir detect_cards).
MIN_SINGLE_CARD_FILL = 0.20


def _is_card_shaped(image: np.ndarray) -> bool:
    height, width = image.shape[:2]
    if height == 0:
        return False
    ratio = width / height
    return any(low <= ratio <= high for low, high in _CARD_RATIO_BANDS)


def _corners_area(corners) -> float:
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


def _whole_image_as_card(image: np.ndarray) -> DetectedCard:
    """Traite l'image entière comme une seule carte (déjà détourée) : image
    au format carte, on la redresse aux dimensions standard. Les corners = les
    4 coins de l'image, pour que l'OCR haute-résolution (extract_card_native)
    reparte de l'original complet."""
    height, width = image.shape[:2]
    corners = [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]]
    warped = _warp_card(image, np.array(corners, dtype="float32"))
    return DetectedCard(index=0, corners=corners, image=warped, preset_index=0)


def _is_single_card_frame(image: np.ndarray, cards: list[DetectedCard]) -> bool:
    """Vrai si l'image est manifestement UNE carte détourée que la détection a
    ratée : image au format carte + plus grosse détection minuscule. Cas réel :
    un scan/visuel plein cadre (carte à l'unité), sur lequel YOLO — entraîné à
    trouver des cartes SUR un fond — s'accroche à un petit motif interne (badge
    Niveau, symbole) au lieu de la carte entière."""
    # Plusieurs cartes détectées = une planche : jamais une carte unique, même
    # si la photo a par hasard un ratio proche d'une carte (constaté : planche
    # 20 cartes en 3024x4032 -> ratio 0,75 -> réduite à tort à une seule carte).
    if len(cards) > 1:
        return False
    if not _is_card_shaped(image):
        return False
    image_area = image.shape[0] * image.shape[1]
    largest = max((_corners_area(c.corners) for c in cards), default=0)
    return largest < MIN_SINGLE_CARD_FILL * image_area


def detect_cards(image: np.ndarray) -> list[DetectedCard]:
    if image is None or image.size == 0:
        return []

    yolo_cards = _detect_cards_yolo(image)
    if yolo_cards:
        # Carte à l'unité déjà détournée mal détectée : on prend l'image entière.
        if _is_single_card_frame(image, yolo_cards):
            return [_whole_image_as_card(image)]
        return yolo_cards

    # Repli contours OpenCV dans deux cas : modèle absent (None) ou modèle
    # présent mais aucune détection plausible ([]) — sur une photo propre
    # (fond uni, scan), les contours restent un filet de secours valable.
    classical = _detect_cards_classical(image)
    if classical and not _is_single_card_frame(image, classical):
        return classical

    # Rien de plausible, mais l'image a le format d'une carte : c'est une carte
    # à l'unité détourée (aucun fond à découper).
    if _is_card_shaped(image):
        return [_whole_image_as_card(image)]
    return classical


def _detect_cards_yolo(image: np.ndarray) -> list[DetectedCard] | None:
    """Détection principale : modèle YOLO entraîné sur des cartes à
    collectionner, bien plus robuste que l'approche par contours sur les fonds
    texturés ou les cartes qui se touchent sans espace. Retourne `None` si le
    modèle n'est pas disponible (pas encore entraîné), pour se rabattre sur
    `_detect_cards_classical`.
    """
    from app.core.card_detector_yolo import detect_cards_yolo

    results = detect_cards_yolo(image)
    if results is None:
        return None

    return [
        DetectedCard(index=r["index"], corners=r["corners"], image=r["image"], preset_index=0)
        for r in results
    ]


def _detect_cards_classical(image: np.ndarray) -> list[DetectedCard]:
    """Détection de secours par contours OpenCV, utilisée uniquement si le
    modèle YOLO n'est pas disponible (voir le docstring du module)."""
    processing_image, scale = _resize_for_processing(image)
    image_area = processing_image.shape[0] * processing_image.shape[1]

    single_quads: list[tuple[float, np.ndarray]] = []
    used_preset_index = 0
    for preset_index, preset in enumerate(CONTOUR_PRESETS):
        contours = _find_card_contours(processing_image, preset)
        candidate_quads, merge_contours = _classify_contours(contours, image_area)

        reference_area = (
            float(np.median([a for a, _ in candidate_quads])) if candidate_quads else None
        )
        for contour in merge_contours:
            candidate_quads.extend(
                _split_merged_contour(processing_image, contour, image_area, reference_area)
            )

        if candidate_quads:
            single_quads = candidate_quads
            used_preset_index = preset_index
            break  # ce réglage a trouvé des cartes plausibles, pas besoin des suivants

    if not single_quads:
        return []

    ordered = _sort_reading_order(single_quads)

    detected = []
    for i, (_, quad) in enumerate(ordered):
        original_quad = quad / scale if scale != 1.0 else quad
        warped = _warp_card(image, original_quad)
        detected.append(
            DetectedCard(
                index=i, corners=original_quad.tolist(), image=warped, preset_index=used_preset_index
            )
        )
    return detected


def _resize_for_processing(image: np.ndarray) -> tuple[np.ndarray, float]:
    h, w = image.shape[:2]
    largest = max(h, w)
    if largest <= MAX_PROCESSING_DIM:
        return image, 1.0
    scale = MAX_PROCESSING_DIM / largest
    resized = cv2.resize(image, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    return resized, scale


def _auto_canny_thresholds(blurred_gray: np.ndarray, sigma: float = 0.33) -> tuple[int, int]:
    median = float(np.median(blurred_gray))
    lower = int(max(0, (1 - sigma) * median))
    upper = int(min(255, (1 + sigma) * median))
    return lower, upper


def _find_card_contours(image: np.ndarray, preset: dict):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_size = preset["blur"]
    blurred = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)

    if preset["canny_low"] == "auto":
        canny_low, canny_high = _auto_canny_thresholds(blurred)
    else:
        canny_low, canny_high = preset["canny_low"], preset["canny_high"]

    edges = cv2.Canny(blurred, canny_low, canny_high)
    kernel = np.ones((preset["close_kernel"], preset["close_kernel"]), np.uint8)
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=preset["close_iterations"])
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return contours


def _estimate_typical_area(areas: list[float], tolerance: float = 0.3) -> float:
    """Estime la taille "typique" d'une carte isolée à partir d'un ensemble de
    contours plausibles par ratio.

    Certains de ces contours peuvent être des fragments parasites (détails
    internes d'une carte — encadré de texte, illustration — qui passent le
    filtre de ratio par coïncidence). Une médiane simple se laisse fausser
    par un mélange de petits fragments et de vraies cartes : elle peut finir
    par désigner à tort de vraies cartes comme "anormalement grandes". On
    cherche plutôt le cluster dominant (la valeur avec le plus de voisins à
    ±30%), en départageant les égalités par l'aire la plus grande — les vraies
    cartes d'une même photo ont une taille très similaire entre elles, alors
    que des fragments parasites sont d'origines diverses et donc plus
    dispersés en taille.
    """
    best_area, best_count = areas[0], 0
    for area in areas:
        count = sum(1 for other in areas if abs(other - area) <= tolerance * area)
        if (count, area) > (best_count, best_area):
            best_count, best_area = count, area
    return best_area


def _classify_contours(contours, image_area: float):
    """Sépare les contours en cartes isolées (ratio carte plausible) et amas
    suspects (aire ou ratio incompatibles avec une carte seule), candidats à
    une tentative de séparation.

    Un amas de cartes qui se chevauchent peut, par coïncidence, avoir un
    ratio de boîte englobante proche de celui d'une carte seule : le ratio
    seul ne suffit donc pas. On fait un premier passage par ratio, puis on
    déclasse en "amas" tout contour dont l'aire dépasse largement la taille
    typique estimée, et on écarte comme fragment parasite tout contour bien
    plus petit qu'elle (une vraie carte plausible par ratio mais 3x plus
    petite que les autres n'est presque jamais une carte, plutôt un détail
    interne d'une carte).
    """
    by_ratio: list[tuple[float, np.ndarray]] = []
    rejected_by_ratio = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < image_area * MIN_AREA_RATIO:
            continue

        (_, _), (w, h), _ = cv2.minAreaRect(contour)
        if w == 0 or h == 0:
            continue

        long_side, short_side = max(w, h), min(w, h)
        ratio = short_side / long_side
        ratio_ok = (
            CARD_ASPECT_RATIO - ASPECT_RATIO_TOLERANCE
            <= ratio
            <= CARD_ASPECT_RATIO + ASPECT_RATIO_TOLERANCE
        )

        if ratio_ok and area <= image_area * MAX_AREA_RATIO:
            by_ratio.append((area, contour))
        elif area <= image_area * MAX_MERGE_AREA_RATIO:
            rejected_by_ratio.append(contour)

    if not by_ratio:
        return [], rejected_by_ratio

    typical_area = _estimate_typical_area([area for area, _ in by_ratio])

    single_quads: list[tuple[float, np.ndarray]] = []
    merge_contours = list(rejected_by_ratio)
    for area, contour in by_ratio:
        if typical_area > 0 and area > typical_area * MERGED_AREA_FACTOR:
            merge_contours.append(contour)
        elif typical_area > 0 and area < typical_area * MIN_TYPICAL_AREA_FACTOR:
            continue  # fragment trop petit pour être une carte plausible, on l'ignore
        else:
            single_quads.append((area, _quad_from_contour(contour)))

    return single_quads, merge_contours


def _quad_from_contour(contour: np.ndarray) -> np.ndarray:
    peri = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
    if len(approx) == 4:
        return approx.reshape(4, 2).astype("float32")
    box = cv2.boxPoints(cv2.minAreaRect(contour))
    return box.astype("float32")


def _split_merged_contour(
    image: np.ndarray, contour: np.ndarray, image_area: float, reference_area: float | None
) -> list[tuple[float, np.ndarray]]:
    """Tente de séparer un contour suspecté de fusionner plusieurs cartes.

    On travaille sur le masque du contour réel (pas un quadrilatère déjà
    simplifié) pour conserver l'éventuelle concavité entre deux cartes qui se
    chevauchent — c'est cette concavité que l'érosion progressive utilise pour
    trouver où couper. Si la séparation échoue, on garde l'amas tel quel
    plutôt que de perdre les cartes qu'il contient.
    """
    fallback = [(cv2.contourArea(contour), _quad_from_contour(contour))]
    if reference_area is None:
        return fallback

    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    cv2.drawContours(mask, [contour], -1, 255, -1)

    markers, num_labels = _find_seed_markers(mask)
    if markers is None:
        return fallback

    sure_fg = np.uint8(markers > 0) * 255
    markers = markers + 1
    unknown = cv2.subtract(mask, sure_fg)
    markers[unknown == 255] = 0

    cv2.watershed(image, markers)

    pieces = []
    for label in range(2, num_labels + 1):
        blob_mask = np.uint8(markers == label) * 255
        sub_contours, _ = cv2.findContours(blob_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not sub_contours:
            continue
        sub_contour = max(sub_contours, key=cv2.contourArea)
        sub_area = cv2.contourArea(sub_contour)
        if sub_area < image_area * MIN_AREA_RATIO:
            continue
        pieces.append((sub_area, _quad_from_contour(sub_contour)))

    return pieces if len(pieces) >= 2 else fallback


def _find_seed_markers(mask: np.ndarray, max_iterations: int = 200):
    """Érode progressivement le masque jusqu'à ce qu'il se scinde en plusieurs
    composantes, utilisées comme germes pour le watershed.

    Plus robuste qu'un seuil fixe sur la distance-transform : un seuil global
    ne détecte pas toujours l'étranglement entre deux cartes qui se
    chevauchent légèrement, alors qu'une érosion progressive finit toujours
    par les séparer avant de les faire disparaître complètement (si une
    séparation géométrique existe).
    """
    kernel = np.ones((3, 3), np.uint8)
    eroded = mask
    for _ in range(max_iterations):
        eroded = cv2.erode(eroded, kernel, iterations=1)
        if cv2.countNonZero(eroded) == 0:
            return None, 0
        num_labels, markers = cv2.connectedComponents(eroded)
        if num_labels >= 3:
            return markers, num_labels
    return None, 0


def _order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # haut-gauche : somme minimale
    rect[2] = pts[np.argmax(s)]  # bas-droite : somme maximale
    diff = np.diff(pts, axis=1).flatten()
    rect[1] = pts[np.argmin(diff)]  # haut-droite
    rect[3] = pts[np.argmax(diff)]  # bas-gauche
    return rect


def _warp_card_to(image: np.ndarray, corners: np.ndarray, out_width: int, out_height: int) -> np.ndarray:
    rect = _order_points(corners)
    tl, tr, br, bl = rect

    width = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
    height = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))

    # Force une orientation portrait, cohérente avec le format d'une carte
    if width > height:
        rect = np.array([rect[1], rect[2], rect[3], rect[0]], dtype="float32")

    dst = np.array(
        [
            [0, 0],
            [out_width - 1, 0],
            [out_width - 1, out_height - 1],
            [0, out_height - 1],
        ],
        dtype="float32",
    )

    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (out_width, out_height))


def _warp_card(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    return _warp_card_to(image, corners, OUTPUT_WIDTH, OUTPUT_HEIGHT)


def extract_card_native(image: np.ndarray, corners, margin: float = 1.0) -> np.ndarray:
    """Warpe une carte à sa résolution NATIVE dans la photo (au moins la
    taille standard des crops). Le crop sauvegardé passe par un
    rééchantillonnage à 480px + une recompression JPEG — deux dégradations
    qui coûtent cher à l'OCR quand la carte ne fait que ~300px dans la photo
    (mesuré : noms d'attaque lisibles depuis la photo originale, illisibles
    depuis le crop sauvegardé). À utiliser comme source OCR quand la photo
    originale est encore disponible.

    `margin` : facteur d'élargissement des coins autour du centre (1.06 =
    +6%). Les boîtes détectées serrent souvent la carte d'un cheveu et
    rognent la toute dernière ligne — celle qui porte le NUMÉRO (constaté :
    "066/217" invisible sans marge, parfaitement lisible avec)."""
    pts = np.array(corners, dtype="float32")
    if margin != 1.0:
        center = pts.mean(axis=0)
        pts = center + (pts - center) * margin
    rect = _order_points(pts)
    tl, tr, br, bl = rect
    width = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
    height = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))
    if width > height:
        width, height = height, width
    out_width = max(int(round(width)), OUTPUT_WIDTH)
    out_height = max(int(round(height)), OUTPUT_HEIGHT)
    return _warp_card_to(image, pts, out_width, out_height)


def _sort_reading_order(candidates: list[tuple[float, np.ndarray]]) -> list[tuple[float, np.ndarray]]:
    """Trie les cartes détectées comme une lecture : ligne par ligne, gauche à droite."""
    if not candidates:
        return candidates

    avg_area = float(np.mean([area for area, _ in candidates]))
    row_height = max(np.sqrt(avg_area), 1.0)

    def sort_key(item):
        _, quad = item
        top_y = float(quad[:, 1].min())
        left_x = float(quad[:, 0].min())
        return (round(top_y / row_height), left_x)

    return sorted(candidates, key=sort_key)
