"""Détection de cartes par un modèle YOLO entraîné (voir
`backend/app/scripts/train_card_yolo.py`), utilisé en détection principale.

Contrairement au pipeline par contours OpenCV (`card_detector.py`), ce modèle
a appris à reconnaître visuellement une carte plutôt que de s'appuyer sur des
heuristiques géométriques (aire, ratio, contours) — beaucoup plus robuste sur
des fonds texturés ou des cartes qui se touchent sans espace, deux cas qui
faisaient concrètement échouer l'approche par contours en usage réel.

Chargement du modèle paresseux et mis en cache (évite de recharger les poids
à chaque requête). Si le fichier de poids n'existe pas encore (pas encore
entraîné), `detect_cards_yolo` retourne `None` pour signaler à l'appelant de
se rabattre sur le pipeline classique.
"""

import cv2
import numpy as np

from app.core.config import CARD_YOLO_MODEL_PATH

CONFIDENCE_THRESHOLD = 0.25
CARD_ASPECT_RATIO = 63 / 88  # largeur / hauteur, format standard carte à jouer — toutes les cartes font la même taille
OUTPUT_WIDTH = 480
OUTPUT_HEIGHT = round(OUTPUT_WIDTH / CARD_ASPECT_RATIO)

# Échelles d'inférence, essayées dans l'ordre jusqu'à obtenir des détections
# plausibles : 640 convient aux planches de plusieurs cartes (la quasi
# totalité des photos), mais une carte scannée plein cadre n'est bien vue
# qu'à plus haute résolution (constaté : 2 boîtes bâclées à 640, 1 boîte
# propre à 960 sur un scan HD).
INFERENCE_SIZES = (640, 960, 1280)

# Filtres géométriques post-détection (voir _filter_boxes) :
PORTRAIT_RATIO_RANGE = (0.55, 0.95)  # carte debout : 63/88 ≈ 0.72
LANDSCAPE_RATIO_RANGE = (1.15, 1.80)  # carte couchée : 88/63 ≈ 1.40
AREA_MEDIAN_RANGE = (0.5, 2.0)  # aire tolérée autour de l'aire médiane
MAX_OVERLAP_RATIO = 0.55  # au-delà, deux boîtes sont des doublons
MIN_BOXES_FOR_AREA_FILTER = 3  # médiane non significative en dessous

# Dernier recours pour une carte plein cadre (scan) : le modèle n'a jamais vu
# ça à l'entraînement (cartes posées dans des scènes) et produit des boîtes
# bâclées à toutes les échelles. Rétrécir la photo au centre d'un canevas
# gris redonne à la carte une taille relative habituelle — validé : boîte
# propre à conf 0,85 sur un scan qui échouait partout ailleurs.
PADDING_FACTOR = 2.5
PADDING_GRAY = 114  # gris du letterbox YOLO, le fond le plus neutre pour le modèle

_model = None
_model_load_attempted = False
_inference_device = "cpu"


def _pick_inference_device() -> str:
    """"mps" (GPU intégré Apple Silicon) quand PyTorch le propose — nettement
    plus rapide qu'en CPU sur un Mac M1/M2 — sinon "cpu" (cas de la VM Linux).
    Même code partout, le matériel disponible est détecté à l'exécution."""
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def _get_model():
    global _model, _model_load_attempted, _inference_device
    if _model is not None:
        return _model
    if _model_load_attempted:
        return None  # déjà tenté et échoué, ne pas boucler dessus à chaque appel

    _model_load_attempted = True
    if not CARD_YOLO_MODEL_PATH.exists():
        return None

    from ultralytics import YOLO

    _inference_device = _pick_inference_device()
    _model = YOLO(str(CARD_YOLO_MODEL_PATH))
    return _model


def warmup() -> None:
    """Charge le modèle et fait une inférence à blanc — appelé en thread au
    démarrage du serveur pour que le premier clic "Découper" ne paie pas les
    ~3s de chargement des poids."""
    model = _get_model()
    if model is not None:
        model.predict(
            np.zeros((640, 640, 3), dtype=np.uint8),
            imgsz=640,
            device=_inference_device,
            verbose=False,
        )


def _predict_boxes(model, image: np.ndarray, imgsz: int) -> list[tuple[tuple, float]]:
    results = model.predict(
        image, conf=CONFIDENCE_THRESHOLD, imgsz=imgsz, device=_inference_device, verbose=False
    )
    boxes = results[0].boxes
    return [
        (tuple(box), float(conf))
        for box, conf in zip(boxes.xyxy.cpu().numpy(), boxes.conf.cpu().numpy())
    ]


def _predict_boxes_padded(model, image: np.ndarray) -> list[tuple[tuple, float]]:
    """Détection sur canevas rembourré (voir PADDING_FACTOR), boîtes ramenées
    dans le repère de la photo d'origine et bornées à ses dimensions."""
    height, width = image.shape[:2]
    canvas = np.full(
        (int(height * PADDING_FACTOR), int(width * PADDING_FACTOR), 3),
        PADDING_GRAY,
        dtype=np.uint8,
    )
    offset_y = (canvas.shape[0] - height) // 2
    offset_x = (canvas.shape[1] - width) // 2
    canvas[offset_y : offset_y + height, offset_x : offset_x + width] = image

    remapped = []
    for (x1, y1, x2, y2), conf in _predict_boxes(model, canvas, 640):
        remapped.append(
            (
                (
                    max(0.0, x1 - offset_x),
                    max(0.0, y1 - offset_y),
                    min(float(width), x2 - offset_x),
                    min(float(height), y2 - offset_y),
                ),
                conf,
            )
        )
    return remapped


def _plausible_ratio(box: tuple) -> bool:
    x1, y1, x2, y2 = box
    height = y2 - y1
    if height <= 0:
        return False
    ratio = (x2 - x1) / height
    return (
        PORTRAIT_RATIO_RANGE[0] <= ratio <= PORTRAIT_RATIO_RANGE[1]
        or LANDSCAPE_RATIO_RANGE[0] <= ratio <= LANDSCAPE_RATIO_RANGE[1]
    )


def _overlap_ratio(a: tuple, b: tuple) -> float:
    """Aire d'intersection rapportée à la plus petite des deux boîtes :
    attrape aussi bien les doublons quasi identiques qu'une boîte incluse
    dans une autre (moitié de carte détectée en plus de la carte entière)."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    intersection = ix * iy
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return intersection / smaller if smaller > 0 else 0.0


def _filter_boxes(detections: list[tuple[tuple, float]]) -> list[tuple]:
    """Nettoie les détections brutes en s'appuyant sur la géométrie connue du
    problème — toutes les cartes physiques font la même taille et le même
    ratio :
    1. ratio hors des plages carte debout/couchée = faux positif (constaté :
       boîtes à ratio 2,2 ou 1,1 sur un scan plein cadre, motifs du fond) ;
    2. doublons/inclusions éliminés au profit de la meilleure confiance ;
    3. aire aberrante vs la médiane = deux cartes fusionnées ou moitié de
       carte (constaté sur fond très texturé) — appliqué seulement à partir
       de quelques boîtes, la médiane n'a pas de sens en dessous.
    """
    plausible = sorted(
        ((box, conf) for box, conf in detections if _plausible_ratio(box)),
        key=lambda item: -item[1],
    )

    kept: list[tuple[tuple, float]] = []
    for box, conf in plausible:
        if all(_overlap_ratio(box, kept_box) < MAX_OVERLAP_RATIO for kept_box, _ in kept):
            kept.append((box, conf))

    if len(kept) >= MIN_BOXES_FOR_AREA_FILTER:
        areas = sorted((b[2] - b[0]) * (b[3] - b[1]) for b, _ in kept)
        median_area = areas[len(areas) // 2]
        kept = [
            (box, conf)
            for box, conf in kept
            if AREA_MEDIAN_RANGE[0] * median_area
            <= (box[2] - box[0]) * (box[3] - box[1])
            <= AREA_MEDIAN_RANGE[1] * median_area
        ]

    return [box for box, _ in kept]


def detect_cards_yolo(image: np.ndarray) -> list[dict] | None:
    """Retourne une liste de cartes détectées (dict avec `corners` et `image`,
    même forme que ce qu'attend `card_detector.detect_cards`), ou `None` si le
    modèle n'est pas disponible (pas encore entraîné)."""
    model = _get_model()
    if model is None:
        return None

    raw_boxes: list[tuple] = []
    for imgsz in INFERENCE_SIZES:
        raw_boxes = _filter_boxes(_predict_boxes(model, image, imgsz))
        if raw_boxes:
            break
    if not raw_boxes:
        raw_boxes = _filter_boxes(_predict_boxes_padded(model, image))
    if not raw_boxes:
        return []

    ordered = _sort_reading_order(raw_boxes)

    detected = []
    for i, box in enumerate(ordered):
        x1, y1, x2, y2 = _expand_box_to_card_ratio(box, image.shape)
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        if crop.shape[1] > crop.shape[0]:  # carte détectée à l'horizontale : redresse en portrait
            crop = cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE)

        # Le crop est déjà au bon ratio (63:88) : ce resize est une mise à
        # l'échelle uniforme, pas un étirement.
        resized = cv2.resize(crop, (OUTPUT_WIDTH, OUTPUT_HEIGHT), interpolation=cv2.INTER_CUBIC)
        corners = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        detected.append({"index": i, "corners": corners, "image": resized})

    return detected


def _expand_box_to_card_ratio(
    box: tuple[float, float, float, float], image_shape: tuple[int, ...]
) -> tuple[int, int, int, int]:
    """Ajuste une boîte détectée pour qu'elle respecte exactement le ratio
    d'une carte (63:88) avant découpe, plutôt que de forcer ce ratio en
    étirant l'image au redimensionnement final.

    Toutes les cartes physiques font la même taille : une boîte qui s'en
    écarte est un défaut d'estimation du modèle (souvent une carte légèrement
    tournée dont la boîte englobante axis-aligned est un peu plus large que
    haute), pas une vraie différence de format. On agrandit toujours la
    dimension la plus courte (jamais de recadrage qui perdrait du contenu).
    """
    x1, y1, x2, y2 = box
    width, height = x2 - x1, y2 - y1
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

    if width / height > CARD_ASPECT_RATIO:
        height = width / CARD_ASPECT_RATIO
    else:
        width = height * CARD_ASPECT_RATIO

    img_h, img_w = image_shape[:2]
    new_x1 = max(0, round(cx - width / 2))
    new_x2 = min(img_w, round(cx + width / 2))
    new_y1 = max(0, round(cy - height / 2))
    new_y2 = min(img_h, round(cy + height / 2))
    return new_x1, new_y1, new_x2, new_y2


def _sort_reading_order(boxes: list[tuple[float, float, float, float]]):
    """Trie les cartes détectées comme une lecture : ligne par ligne, gauche à
    droite (même logique que `card_detector._sort_reading_order`, adaptée aux
    boîtes englobantes x1,y1,x2,y2 plutôt qu'aux quadrilatères)."""
    if not boxes:
        return boxes

    avg_area = float(np.mean([(x2 - x1) * (y2 - y1) for x1, y1, x2, y2 in boxes]))
    row_height = max(np.sqrt(avg_area), 1.0)

    def sort_key(box):
        x1, y1, _, _ = box
        return (round(y1 / row_height), x1)

    return sorted(boxes, key=sort_key)
