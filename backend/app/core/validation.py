"""Validation des identifiants reçus dans les URLs.

`photo_id` et `crop_filename` servent à construire des chemins sur le disque
(`data/uploads/crops/{photo_id}/{crop_filename}`...) : sans validation, un
identifiant contenant `../` permettrait de lire/écrire hors des dossiers de
données (traversée de chemin). L'app est LAN-only, mais le garde-fou est
trivial et le format légitime est connu : UUID pour les photos (générés par
`uploads.py`), `card_NN.jpg` pour les crops (générés par `crops.py`).
"""

import re

from fastapi import HTTPException

# UUID généré par uploads.py — on tolère tout alphanumérique/tiret de taille
# raisonnable plutôt qu'un strict UUID, pour ne pas casser d'anciens ids.
_PHOTO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9-]{1,64}$")
_CROP_FILENAME_PATTERN = re.compile(r"^card_\d{1,4}\.jpg$")


def validate_photo_id(photo_id: str) -> str:
    if not _PHOTO_ID_PATTERN.fullmatch(photo_id):
        raise HTTPException(status_code=400, detail="Identifiant de photo invalide.")
    return photo_id


def validate_crop_filename(crop_filename: str) -> str:
    if not _CROP_FILENAME_PATTERN.fullmatch(crop_filename):
        raise HTTPException(status_code=400, detail="Nom de crop invalide.")
    return crop_filename
