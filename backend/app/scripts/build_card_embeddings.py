"""Construit l'index d'embeddings DINOv2 de toutes les cartes de référence.

Étape unique (à relancer seulement quand le cache de cartes change) : parcourt
les vignettes de `reference_thumbnails/`, calcule l'embedding de chacune par
lots, et sauvegarde une matrice `card_embeddings.npy` [N, D] alignée sur
`card_embeddings_ids.json`. Ces fichiers sont ensuite chargés par
`card_identifier` pour le repli embeddings sur les cartes foil/gold.

Reprend là où il s'était arrêté grâce à un point de sauvegarde périodique :
sur la VM (~40 min) comme sur un M1 (~quelques minutes), une interruption ne
gâche pas tout le travail.

Usage : python -m app.scripts.build_card_embeddings
"""

import json
import time

import cv2
import numpy as np

from app.core.card_embedder import embed_batch, is_available
from app.core.config import DB_DIR, REFERENCE_THUMBNAILS_DIR

EMBEDDINGS_PATH = DB_DIR / "card_embeddings.npy"
IDS_PATH = DB_DIR / "card_embeddings_ids.json"
BATCH_SIZE = 32
CHECKPOINT_EVERY = 40  # lots entre deux sauvegardes


def _load_progress() -> dict[str, np.ndarray]:
    """Embeddings déjà calculés, indexés par card_id (pour la reprise)."""
    if EMBEDDINGS_PATH.exists() and IDS_PATH.exists():
        ids = json.loads(IDS_PATH.read_text())
        matrix = np.load(EMBEDDINGS_PATH)
        if len(ids) == len(matrix):
            return {cid: matrix[i] for i, cid in enumerate(ids)}
    return {}


def _save(done: dict[str, np.ndarray]) -> None:
    ids = list(done.keys())
    matrix = np.stack([done[cid] for cid in ids]).astype(np.float32)
    np.save(EMBEDDINGS_PATH, matrix)
    IDS_PATH.write_text(json.dumps(ids))


def main() -> None:
    if not is_available():
        raise SystemExit(
            "DINOv2 indisponible (torch non installé ou téléchargement des poids échoué). "
            "Le repli embeddings restera inactif ; l'identification pHash/ORB continue de fonctionner."
        )

    all_ids = sorted(p.stem for p in REFERENCE_THUMBNAILS_DIR.glob("*.jpg"))
    done = _load_progress()
    todo = [cid for cid in all_ids if cid not in done]
    print(f"{len(all_ids)} cartes | déjà faites : {len(done)} | à traiter : {len(todo)}", flush=True)

    start = time.perf_counter()
    for batch_index in range(0, len(todo), BATCH_SIZE):
        batch_ids = todo[batch_index : batch_index + BATCH_SIZE]
        images, valid_ids = [], []
        for cid in batch_ids:
            img = cv2.imread(str(REFERENCE_THUMBNAILS_DIR / f"{cid}.jpg"))
            if img is not None:
                images.append(img)
                valid_ids.append(cid)
        if images:
            vectors = embed_batch(images)
            for cid, vec in zip(valid_ids, vectors):
                done[cid] = vec

        batch_number = batch_index // BATCH_SIZE
        if batch_number and batch_number % CHECKPOINT_EVERY == 0:
            _save(done)
            elapsed = time.perf_counter() - start
            processed = batch_index + len(batch_ids)
            rate = processed / elapsed if elapsed else 0
            remaining = (len(todo) - processed) / rate if rate else 0
            print(
                f"  {len(done)}/{len(all_ids)} — {rate:.1f} cartes/s — reste ~{remaining/60:.0f} min",
                flush=True,
            )

    _save(done)
    print(f"Terminé : {len(done)} embeddings en {(time.perf_counter()-start)/60:.1f} min → {EMBEDDINGS_PATH}", flush=True)


if __name__ == "__main__":
    main()
