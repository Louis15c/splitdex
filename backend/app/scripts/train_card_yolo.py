"""Entraîne un modèle YOLO léger pour détecter des cartes à collectionner sur
une photo, à partir du dataset Roboflow "Trading Card Detection" forké dans
le workspace personnel de l'utilisateur (le projet public d'origine
n'autorise pas la génération de version via l'API pour un compte tiers) :
https://universe.roboflow.com/tcg-5rc9r/trading-card-detection

Remplace la détection par contours OpenCV (`card_detector.py`) quand celle-ci
échoue sur des fonds texturés ou des cartes qui se touchent sans espace —
des cas où l'absence de compréhension sémantique de "à quoi ressemble une
carte" fait échouer toute heuristique géométrique.

Usage (depuis backend/, venv activé) :
    python -m app.scripts.train_card_yolo
    python -m app.scripts.train_card_yolo --epochs 50

Nécessite une clé API Roboflow gratuite (https://roboflow.com) dans `.env`
(ROBOFLOW_API_KEY=...) — utilisée une seule fois pour générer et télécharger
le dataset ; l'entraînement et l'inférence ensuite sont 100% locaux.
"""

import argparse
import shutil
from pathlib import Path

import yaml

from app.core.config import CARD_YOLO_MODEL_PATH, MODELS_DIR, ROBOFLOW_API_KEY

# Fork personnel du dataset public, dans le workspace de l'utilisateur (le
# projet d'origine tcg-5rc9r/trading-card-detection n'autorise pas la
# génération de version via l'API pour un compte qui ne le possède pas).
ROBOFLOW_WORKSPACE = "walters-workspace-akqez"
ROBOFLOW_PROJECT = "trading-card-detection-tovvj"
DATASET_DIR = MODELS_DIR / "dataset"


def _fix_data_yaml_paths(dataset_dir: Path) -> None:
    """Le data.yaml exporté par Roboflow utilise des chemins relatifs
    (`../train/images`) qui supposent que train/valid/test sont au-dessus du
    dossier du dataset — faux ici, ils sont dedans. Sans `path:` absolu,
    Ultralytics résout ces chemins relatifs à son `datasets_dir` global, pas
    au dossier réel du dataset, et ne trouve rien.
    """
    data_yaml = dataset_dir / "data.yaml"
    config = yaml.safe_load(data_yaml.read_text())
    config["path"] = str(dataset_dir)
    config["train"] = "train/images"
    config["val"] = "valid/images"
    config["test"] = "test/images"
    data_yaml.write_text(yaml.safe_dump(config))


def download_dataset() -> Path:
    from roboflow import Roboflow

    if not ROBOFLOW_API_KEY:
        raise SystemExit(
            "ROBOFLOW_API_KEY manquant dans .env. Crée une clé gratuite sur "
            "https://roboflow.com et ajoute-la à .env (voir .env.example)."
        )

    rf = Roboflow(api_key=ROBOFLOW_API_KEY)
    project = rf.workspace(ROBOFLOW_WORKSPACE).project(ROBOFLOW_PROJECT)

    versions = project.versions()
    if versions:
        version = max(v.version for v in versions)
    else:
        print("Aucune version existante, génération d'une nouvelle version...")
        version = project.generate_version(
            settings={
                "augmentation": {},
                "preprocessing": {
                    "auto-orient": True,
                    "resize": {"width": 640, "height": 640, "format": "Stretch to"},
                },
            }
        )

    if DATASET_DIR.exists():
        shutil.rmtree(DATASET_DIR)
    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    dataset = project.version(version).download("yolov8", location=str(DATASET_DIR))
    dataset_path = Path(dataset.location)
    _fix_data_yaml_paths(dataset_path)
    print(f"Dataset téléchargé dans {dataset_path}")
    return dataset_path


def train(dataset_dir: Path, epochs: int, imgsz: int, batch: int) -> Path:
    from ultralytics import YOLO

    data_yaml = dataset_dir / "data.yaml"
    if not data_yaml.exists():
        raise SystemExit(f"Fichier data.yaml introuvable dans {dataset_dir}")

    model = YOLO("yolov8n.pt")  # nano : le plus léger, suffisant pour une seule classe "carte"
    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        workers=2,  # peu de RAM disponible : limite le nombre de processus de chargement
        project=str(MODELS_DIR / "runs"),
        name="card_detector",
        exist_ok=True,
    )

    best_weights = Path(results.save_dir) / "weights" / "best.pt"
    if not best_weights.exists():
        raise SystemExit(f"Poids entraînés introuvables : {best_weights}")

    CARD_YOLO_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(best_weights, CARD_YOLO_MODEL_PATH)
    print(f"Modèle entraîné copié vers {CARD_YOLO_MODEL_PATH}")
    return CARD_YOLO_MODEL_PATH


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=50, help="Nombre d'époques d'entraînement")
    parser.add_argument("--imgsz", type=int, default=640, help="Taille d'image d'entraînement")
    parser.add_argument("--batch", type=int, default=16, help="Taille de batch (réduire si RAM limitée)")
    parser.add_argument("--skip-download", action="store_true", help="Réutilise le dataset déjà téléchargé")
    args = parser.parse_args()

    dataset_path = DATASET_DIR if args.skip_download else download_dataset()
    train(dataset_path, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch)
