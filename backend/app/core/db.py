import sqlite3
from contextlib import contextmanager

from app.core.config import SQLITE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS reference_cards (
    id TEXT PRIMARY KEY,          -- id pokemontcg.io, ex: "swsh1-1"
    name TEXT NOT NULL,
    set_id TEXT NOT NULL,
    set_name TEXT NOT NULL,
    series TEXT,                   -- bloc/série (ex: "Sword & Shield"), traduit en FR à l'affichage
    number TEXT NOT NULL,
    printed_total INTEGER,
    rarity TEXT,
    small_image_url TEXT NOT NULL,
    large_image_url TEXT,
    phash TEXT NOT NULL,          -- perceptual hash (hex), calculé depuis small_image_url
    synced_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reference_cards_set ON reference_cards (set_id);

CREATE TABLE IF NOT EXISTS identifications (
    photo_id TEXT NOT NULL,
    crop_filename TEXT NOT NULL,
    card_id TEXT,                 -- NULL si aucune correspondance jugée fiable
    orb_score INTEGER,            -- nb de bons points d'intérêt ORB en commun (plus haut = plus fiable)
    candidates_json TEXT NOT NULL, -- top-k candidats [{card_id, phash_distance, orb_score}, ...]
    language TEXT,                 -- langue d'impression détectée par OCR (NULL = indéterminée)
    created_at TEXT NOT NULL,
    PRIMARY KEY (photo_id, crop_filename)
);

CREATE TABLE IF NOT EXISTS listings (
    photo_id TEXT NOT NULL,
    crop_filename TEXT NOT NULL,
    card_id TEXT NOT NULL,        -- carte retenue pour la fiche (identifiée, corrigible en Phase 5)
    condition TEXT NOT NULL,
    price REAL,                   -- NULL tant que le prix n'a pas été saisi (Phase 5)
    language TEXT,                 -- NULL ou "Français" = pas mentionné dans le texte ; sinon mentionné
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (photo_id, crop_filename)
);
"""

# Colonnes ajoutées après la création initiale des tables : ALTER TABLE plutôt
# que de recréer, pour ne pas perdre le cache pokemontcg.io déjà synchronisé.
MIGRATIONS = [
    ("identifications", "language", "TEXT"),
    ("listings", "language", "TEXT"),
    ("reference_cards", "series", "TEXT"),
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _apply_migrations(conn: sqlite3.Connection) -> None:
    for table, column, col_type in MIGRATIONS:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        _apply_migrations(conn)


@contextmanager
def db_cursor():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    finally:
        conn.close()
