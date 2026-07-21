"""Embeddings d'images de cartes via DINOv2 (modèle LOCAL, aucun appel réseau
à l'inférence — seuls les poids sont téléchargés une fois, comme pour YOLO).

Pourquoi : le pHash (hash global) et l'ORB (points d'intérêt locaux) s'effondrent
sur les cartes à foil doré / holographiques lourdes (mesuré : ORB ~8-12 même
contre la bonne référence, le reflet métallique détruit points d'intérêt ET
hash). Un réseau auto-supervisé produit un vecteur dense qui capte le CONTENU
de l'illustration, robuste au foil, à l'éclairage et à l'écart photo↔scan
(mesuré sur DINOv2 ViT-S : Ténéfix reverse-holo+watermark → la bonne carte en
rang 0 ; Zoroark BREAK gold → rang 4, contre des centaines de rangs pour
pHash). Utilisé UNIQUEMENT en repli quand la voie pHash/ORB est peu sûre : le
modèle est plus lent (~0,3-0,5s/image CPU), inutile de le payer sur les cartes
classiques déjà bien identifiées.

L'embedding n'est PAS invariant à la rotation : on embarque le crop aux 4
orientations et on garde la meilleure (gère les cartes BREAK/TURBO horizontales
et les photos tête-bêche, comme la voie ORB).
"""

import os
import threading

import cv2
import numpy as np

MODEL_INPUT_SIZE = 224  # multiple de 14 (patch DINOv2) → 16×16 patches
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

_model = None
_device = None
_model_lock = threading.Lock()


def _pick_device():
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _load_model():
    """Chargement paresseux et thread-safe du modèle DINOv2. Retourne
    `(model, device)` ou `(None, None)` si torch/DINOv2 indisponible — dans ce
    cas l'appelant se rabat simplement sur la voie pHash/ORB (rien ne plante)."""
    global _model, _device
    if _model is not None or _device == "unavailable":
        return _model, _device
    with _model_lock:
        if _model is not None or _device == "unavailable":
            return _model, _device
        try:
            import torch

            torch.set_num_threads(os.cpu_count() or 4)
            device = _pick_device()
            model = torch.hub.load("facebookresearch/dinov2", "dinov2_vits14", verbose=False)
            model.eval().to(device)
            _model, _device = model, device
        except Exception:
            _device = "unavailable"
            _model = None
        return _model, _device


def is_available() -> bool:
    model, _ = _load_model()
    return model is not None


def _preprocess(image_bgr: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE), interpolation=cv2.INTER_AREA)
    normalized = (resized.astype(np.float32) / 255.0 - _IMAGENET_MEAN) / _IMAGENET_STD
    return np.transpose(normalized, (2, 0, 1))  # HWC → CHW


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    return matrix / np.maximum(norms, 1e-8)


def embed_batch(images_bgr: list[np.ndarray]) -> np.ndarray | None:
    """Embeddings L2-normalisés d'un lot d'images (float32, shape [N, D]).
    `None` si le modèle est indisponible."""
    model, device = _load_model()
    if model is None:
        return None
    import torch

    batch = np.stack([_preprocess(img) for img in images_bgr])
    with torch.no_grad():
        tensor = torch.from_numpy(batch).to(device)
        vectors = model(tensor).cpu().numpy().astype(np.float32)
    return _l2_normalize(vectors)


def embed_image(image_bgr: np.ndarray) -> np.ndarray | None:
    result = embed_batch([image_bgr])
    return None if result is None else result[0]


def embed_rotations(image_bgr: np.ndarray) -> np.ndarray | None:
    """Embeddings des 4 orientations du crop (0/90/180/270°), shape [4, D].
    L'embedding n'étant pas invariant à la rotation, l'appelant retient la
    meilleure similarité sur ces 4 vues."""
    rotations = [
        image_bgr,
        cv2.rotate(image_bgr, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(image_bgr, cv2.ROTATE_180),
        cv2.rotate(image_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE),
    ]
    return embed_batch(rotations)
