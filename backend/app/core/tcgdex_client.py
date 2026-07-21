"""Client minimal pour l'API publique TCGdex (https://tcgdex.dev), utilisée
uniquement pour récupérer une estimation de prix (Cardmarket, en EUR) —
pokemontcg.io ne fournit aucune donnée de prix.

Pas de clé requise, API ouverte. Recherche par nom + numéro plutôt que par
identifiant : les identifiants TCGdex ne correspondent pas à ceux de
pokemontcg.io (ex: set "151" = `sv3pt5` chez pokemontcg.io, `sv03.5` chez
TCGdex ; le japonais est un catalogue à part entière, ex: `SV2a`), donc pas de
table de correspondance à maintenir — on cherche à la volée par (nom,
numéro), qui eux sont des attributs stables des deux côtés.
"""

import threading

import httpx

BASE_URL = "https://api.tcgdex.net/v2"
# Une estimation enchaîne jusqu'à 4 requêtes (recherche + détail, x2 langues) :
# un timeout court garde le pire cas raisonnable pour un clic dans l'UI.
TIMEOUT = 8.0

# Client partagé : réutilise les connexions TCP/TLS entre les requêtes (une
# estimation en fait plusieurs, et l'UI en déclenche carte après carte).
_client: httpx.Client | None = None
_client_lock = threading.Lock()


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)
    return _client


def _normalize_local_id(local_id: str) -> str:
    return local_id.lstrip("0") or "0"


def find_card(name: str, number: str, locale: str = "en") -> dict | None:
    """Cherche la carte TCGdex correspondant à `name`/`number` dans le
    catalogue de la langue `locale` ("en" pour l'anglais/international — même
    catalogue que le français/allemand/espagnol/italien, voir
    `price_estimator.py` — ou "ja" pour le catalogue japonais, distinct).

    Retourne le détail complet de la carte (avec pricing) si trouvée avec
    confiance (un seul candidat au numéro demandé), sinon `None`.
    """
    target_number = _normalize_local_id(number)
    client = _get_client()

    try:
        response = client.get(f"/{locale}/cards", params={"name": name})
        if response.status_code != 200:
            return None
        candidates = [
            c for c in response.json() if _normalize_local_id(c.get("localId", "")) == target_number
        ]
        if len(candidates) != 1:
            return None

        detail_response = client.get(f"/{locale}/cards/{candidates[0]['id']}")
        if detail_response.status_code != 200:
            return None
        return detail_response.json()
    except httpx.HTTPError:
        return None
