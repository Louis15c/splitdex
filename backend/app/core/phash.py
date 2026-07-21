"""Empreinte perceptuelle (perceptual hash) pour le matching d'images de cartes.

Deux images visuellement proches (même carte, léger écart de cadrage/luminosité)
ont un hash à faible distance de Hamming, contrairement à des images
différentes. C'est beaucoup plus tolérant qu'une comparaison pixel à pixel,
sans nécessiter d'entraînement d'un modèle.
"""

import io

import imagehash
import numpy as np
from PIL import Image


def compute_phash(image_bgr: np.ndarray) -> str:
    rgb = image_bgr[:, :, ::-1]  # BGR (OpenCV) -> RGB (Pillow)
    pil_image = Image.fromarray(rgb)
    return str(imagehash.phash(pil_image))


def compute_phash_from_bytes(image_bytes: bytes) -> str:
    pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return str(imagehash.phash(pil_image))


def hamming_distance(hash_a: str, hash_b: str) -> int:
    return imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b)
