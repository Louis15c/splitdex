"""Identification d'une carte découpée contre le cache local de cartes de
référence (pokemontcg.io).

Stratégies de présélection, essayées dans l'ordre :
1. **Indices numéro + nom (OCR)** : le numéro imprimé ("170/165") et le nom
   de l'espèce (gros caractères en haut de la carte) sont lus par OCR quand
   possible. S'ils identifient un candidat, on ne compare l'artwork qu'à ce
   sous-ensemble réduit (une poignée de cartes) plutôt qu'à tout le
   catalogue — plus précis, et le numéro est indépendant de la langue
   d'impression (chiffres identiques en français/anglais/japonais/etc.,
   contrairement au texte).
2. **pHash sur tout le catalogue**, si l'OCR échoue ou ne donne rien
   d'assez confiant : présélection rapide (vectorisée avec numpy) mais
   moins fine (un crop réel passe par une correction de perspective qui
   introduit un flou d'interpolation, ce qui peut mettre plusieurs cartes au
   coude à coude en distance de Hamming).

Dans tous les cas, la présélection est ensuite reclassée par feature
matching ORB — beaucoup plus discriminant qu'un hash global car il compare
des points d'intérêt locaux, donc plus tolérant au flou/à la perspective.
Testé en pratique : ~130-450 correspondances ORB pour la bonne carte contre
~5-20 pour une carte proche mais différente.
"""

import json
import re
from dataclasses import dataclass, replace

import cv2
import numpy as np

from app.core.card_embedder import embed_image, embed_rotations
from app.core.config import DB_DIR, REFERENCE_THUMBNAILS_DIR, SQLITE_PATH
from app.core.db import db_cursor
from app.core.name_detector import detect_pokemon_name_hint, japanese_name_confirms
from app.core.number_detector import detect_card_number
from app.core.phash import compute_phash

HASH_BITS = 64  # taille du hash perceptuel par défaut (imagehash.phash, 8x8)
# Nombre de candidats retenus par pHash avant reclassement ORB. Le pHash est
# un hash GLOBAL : bon rappel sur une carte classique, mais mauvais sur les
# full-arts / illustration-rares (l'illustration plein cadre + le texte d'une
# autre langue décalent le hash, la bonne carte peut tomber au 300e rang).
# L'ORB, lui, discrimine très bien ces cartes (mesuré : Plusle AR japonaise →
# ORB 54 contre la bonne carte anglaise, mais rang pHash 287). On élargit donc
# fortement la présélection image pour que l'ORB ait sa chance ; c'est lui qui
# tranche. Coût payé seulement sur la voie image (cartes dont l'OCR n'a donné
# aucun indice fiable), pas sur les cartes classiques identifiées par nom/numéro.
# ── Voie rapide : reconnaissance par empreinte, sans lire un caractère ────
# C'est la méthode des applications de tri de cartes : comparer une empreinte
# visuelle de la photo à un index pré-calculé, puis confirmer le meilleur
# candidat. La recherche porte sur 20 000 cartes et coûte ~15 ms ; l'essentiel
# du temps est le calcul de l'empreinte (~140 ms).
#
# Mesuré sur les 24 cartes des deux photos de référence : 201 ms par carte
# contre ~3 000 ms pour la voie complète, pour 21 identifications justes sur
# 24. Les 3 fausses ressortent avec un ORB de 2, 10 et 12 — toutes sous le
# seuil ci-dessous, tandis que les 21 justes sont toutes au-dessus. Un ORB
# faible signale donc précisément les cas où il ne faut PAS conclure ici.
FAST_TOP_K = 5
FAST_MIN_ORB = 20
# Écart minimal entre le meilleur candidat et le suivant. Un score ORB élevé ne
# suffit PAS : sur une réédition, l'illustration est rigoureusement la même dans
# deux extensions, les deux candidats matchent donc aussi bien l'un que l'autre
# et l'ORB confirme l'ILLUSTRATION, pas la carte. Constaté sur l'historique :
# Venusaur Celebrations n°15 pris pour Venusaur Legendary Collection n°18 à
# ORB 79, Venonat Jungle n°63 pour Venonat Base Set 2 n°97 à ORB 37. Seuls le
# symbole d'extension et le numéro les séparent — ce que seule la voie complète
# lit.
#
# Mesuré sur 612 identifications d'historique, 19 décisions fausses contre 120
# justes : marge médiane de 6 pour les fausses (minimum 0), 52 pour les justes.
# Le balayage des seuils donne, en erreurs restantes / décisions conservées :
#     marge >= 5   84% / 97%      marge >= 15  16% / 88%
#     marge >= 10  32% / 92%      marge >= 20  11% / 87%
# À 20 on écarte 89% des erreurs en ne renonçant qu'à 13% des décisions
# rapides, lesquelles repartent en voie complète : elles ne sont pas perdues,
# seulement plus lentes.
FAST_MIN_ORB_MARGIN = 20
# Une seule orientation, contrairement à `_match_by_embedding` : une carte
# pivotée échouera simplement la confirmation et repassera par la voie
# complète, qui sait la retourner. Payer 4 orientations ici coûterait 2,5x
# plus cher à toutes les cartes pour rattraper un cas rare.

IMAGE_SHORTLIST_SIZE = 400
# Présélection réduite pour les orientations pivotées (voir identify) : la
# rotation est testée 3 fois, une grande liste y coûterait trop cher.
ROTATION_SHORTLIST_SIZE = 40
ORB_FEATURES = 500
ORB_GOOD_MATCH_MAX_DISTANCE = 50  # distance de descripteur (Hamming) en dessous de laquelle un match est "bon"
# En dessous de ce score ORB, on ne fait pas confiance à l'indice numéro/nom
# (OCR probablement faux) et on retombe sur la présélection pHash classique.
# En dessous de ce score ORB à 0°, on soupçonne une carte pivotée et on
# teste les autres orientations (voir identify). Au-dessus, la carte est
# clairement reconnue droite : on n'y touche pas.
ROTATION_ORB_TRIGGER = 20
# Marge minimale pour préférer une orientation pivotée à l'orientation droite.
ROTATION_SWITCH_MARGIN = 8

# Au-dessus de ce score ORB, un indice de nom/numéro est jugé sûr et renvoyé
# directement (voie rapide). En dessous, on le met en concurrence avec la voie
# image (grande présélection) et on garde le meilleur ORB — un nom d'espèce mal
# lu produit un ORB faible que la vraie carte dépasse.
STRONG_HINT_ORB = 16

# Repli embeddings DINOv2 (voir card_embedder) : déclenché uniquement quand le
# meilleur ORB reste faible (cartes foil/holo où le pHash global échoue à
# présélectionner la bonne carte). On calcule l'embedding du crop (4
# orientations), on présélectionne par cosinus, puis l'ORB confirme : on
# n'adopte le résultat que si son ORB dépasse l'existant ET atteint un vrai
# seuil de confiance (pas un match ORB marginal).
EMBED_FALLBACK_ORB = 20
EMBED_TOP_K = 10
EMBED_CONFIRM_MIN_ORB = 18
# Un match par PURE image (sans indice de nom) à ORB moyen est peu fiable sur
# les full-arts : l'illustration plein cadre matche des cartes au hasard à ORB
# 20-40 (mesuré : Pidgeot-EX full-art → "Potion" ORB 21). En dessous de ce
# seuil et sans indice de nom, on consulte donc aussi l'embedding.
EMBED_PURE_IMAGE_ORB = 45
# Seuil de confiance cosinus pour adopter l'embedding SANS confirmation ORB
# (l'ORB ne sait pas confirmer un full-art). Élevé à dessein : au-dessus, les
# full-arts corrects (Pidgeot 0.83, Garchomp SIR 0.79) ; en dessous, les
# confusions entre cartes gold (Sharpedo 0.64, Flareon 0.73). Avance minimale
# sur le 2e pour écarter les quasi-égalités.
EMBED_COS_TRUST = 0.78
EMBED_COS_MARGIN = 0.04

NUMBER_HINT_MIN_ORB_SCORE = 15
# Repli : un score plus faible reste acceptable si le candidat devance
# nettement le suivant (marge relative) — l'indice nom/numéro a déjà réduit
# le champ à une poignée de candidats, donc une nette avance dans ce petit
# lot est un signal fort même quand le score absolu reste bas (crop de
# moins bonne qualité). Validé en pratique : un cas réel avec un score ORB
# de seulement 13 (sous le seuil absolu) mais 2x le suivant (6).
NUMBER_HINT_MIN_ORB_SCORE_WITH_MARGIN = 10
NUMBER_HINT_MIN_MARGIN_RATIO = 2.0


@dataclass
class MatchCandidate:
    card_id: str
    name: str
    set_name: str
    number: str
    rarity: str | None
    small_image_url: str
    phash_distance: int | None = None
    orb_score: int = 0
    embed_sim: float = 0.0  # similarité cosinus DINOv2 (repli foil/gold)
    matched_by: str = "image"  # "number" si trouvée via l'indice numéro OCR


@dataclass
class IdentificationResult:
    candidates: list[MatchCandidate]
    # Langue passée en entrée, éventuellement précisée si `detect_language`
    # était indéterminé (`None`) mais que l'indice nom a trouvé une
    # correspondance exacte dans une table de langue donnée — un signal au
    # moins aussi fiable que les mots-clés génériques de `detect_language`
    # (voir `name_detector.detect_pokemon_name_hint`).
    language: str | None


class ReferenceIndex:
    def __init__(self, rows: list[dict], bit_matrix: np.ndarray):
        self._rows = rows
        self._bit_matrix = bit_matrix
        self._row_by_id = {row["id"]: row for row in rows}

    def is_empty(self) -> bool:
        return len(self._rows) == 0

    def identify(
        self,
        crop_image_bgr: np.ndarray,
        top_k: int = 3,
        language: str | None = None,
        text: str | None = None,
        number_hint: tuple[str, str] | None = None,
    ) -> IdentificationResult:
        """`text` : résultat d'`ocr_text` déjà calculé pour ce crop, à fournir
        quand l'appelant a déjà fait de l'OCR (ex: `detect_language`) — sinon
        chaque détecteur relancerait sa propre passe OCR (~3s chacune).

        `number_hint` : numéro déjà lu par l'appelant (passe ciblée sur la
        photo d'origine, cf. `number_detector.detect_card_number_focused`), qui
        a accès à une image mieux cadrée que ce crop."""
        if self.is_empty():
            return IdentificationResult(candidates=[], language=language)

        number_hint = number_hint or detect_card_number(crop_image_bgr, text=text)
        number = number_hint[0] if number_hint else None
        name_hint_en, name_hint_language = detect_pokemon_name_hint(crop_image_bgr, language, text=text)
        effective_language = language if language is not None else name_hint_language

        # Match par indice OCR (nom/numéro), s'il donne une shortlist.
        hint_result = None  # (candidats reclassés, libellé matched_by)
        if number or name_hint_en:
            hinted_shortlist = self._shortlist_by_hints(number, name_hint_en)
            reranked = None
            if not hinted_shortlist and number and name_hint_en:
                # Numéro et nom incompatibles : l'un des deux est mal lu, et on
                # ne sait pas lequel a priori. On explore donc les DEUX pistes
                # et on garde celle que l'image confirme le mieux (ORB) — à
                # égalité le numéro l'emporte, car il désigne une carte unique
                # dans son set alors qu'un nom peut venir du texte d'ambiance
                # (constaté : "Chrysapile" lu sur une carte Lucanon, qui
                # renvoyait vers la mauvaise extension malgré un numéro net).
                by_number = _rerank_by_orb(crop_image_bgr, self._shortlist_by_hints(number, None))
                by_name = _rerank_by_orb(crop_image_bgr, self._shortlist_by_hints(None, name_hint_en))
                score_number = by_number[0].orb_score if by_number else -1
                score_name = by_name[0].orb_score if by_name else -1
                if score_number >= score_name:
                    reranked, name_hint_en = by_number, None
                else:
                    reranked, number = by_name, None
                hinted_shortlist = reranked
            if hinted_shortlist:
                if reranked is None:
                    reranked = _rerank_by_orb(crop_image_bgr, hinted_shortlist)
                if reranked:
                    matched_by = "+".join(
                        filter(None, ["number" if number else None, "name" if name_hint_en else None])
                    )
                    for candidate in reranked:
                        candidate.matched_by = matched_by
                    hint_result = reranked
                    # Un indice FORT (ORB élevé) est quasi certain : on le
                    # renvoie tout de suite, sans payer la voie image. En
                    # dessous, on ne lui fait plus une confiance aveugle : un
                    # nom d'espèce mal lu (ligne d'évolution, OCR foil) donne
                    # une shortlist hors sujet au meilleur ORB faible, alors
                    # que la voie image retrouve souvent la vraie carte avec un
                    # ORB bien supérieur (mesuré : Lucanon nom→Charjabug ORB 15
                    # mais image→Vikavolt ORB 51 ; Garchomp nom→Paras ORB 6,
                    # image→ORB 12). On la compare donc à la voie image plus bas
                    # et on garde le meilleur ORB.
                    if reranked[0].orb_score >= STRONG_HINT_ORB:
                        return IdentificationResult(candidates=reranked[:top_k], language=effective_language)

        best = self._match_by_image(crop_image_bgr, IMAGE_SHORTLIST_SIZE)

        # Cartes pivotées : les cartes BREAK/TURBO ont une illustration en
        # paysage, souvent photographiées à l'horizontale, et une photo peut
        # être tête-bêche. Le crop est alors tourné de 90/180/270° par rapport
        # à la vignette de référence (portrait) et l'ORB s'effondre. Quand le
        # meilleur score à 0° est faible, on retente les trois autres
        # orientations et on garde la meilleure — coût payé seulement sur les
        # cas douteux, le cas courant (carte droite bien reconnue) sort direct.
        top_score = best[0].orb_score if best else 0
        if top_score < ROTATION_ORB_TRIGGER:
            baseline = top_score
            for rotate_code in (cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE):
                rotated = cv2.rotate(crop_image_bgr, rotate_code)
                candidate = self._match_by_image(rotated, ROTATION_SHORTLIST_SIZE)
                # On ne bascule que si l'orientation pivotée est NETTEMENT
                # meilleure : un vrai pivot fait bondir l'ORB (8 → 40+),
                # alors qu'un écart d'un ou deux points n'est que du bruit et
                # ne doit pas renverser un match droit correct au score limite.
                if candidate and candidate[0].orb_score > max(baseline + ROTATION_SWITCH_MARGIN, best[0].orb_score if best else 0):
                    best = candidate

        # Indice de nom faible mis en concurrence avec la voie image : on garde
        # celui qui a le meilleur ORB. À égalité, l'indice l'emporte (le nom lu
        # reste un a priori utile ; ex. lever une ambiguïté entre deux sets de
        # la même espèce au même score).
        if hint_result and (not best or hint_result[0].orb_score >= best[0].orb_score):
            best = hint_result

        # Repli embeddings : uniquement si tout ce qui précède reste faible en
        # ORB (typiquement une carte foil/holo que ni pHash ni ORB ne savent
        # présélectionner). L'embedding sert de RAPPEL — il propose la bonne
        # carte que le pHash global manque — et l'ORB CONFIRME. On n'adopte le
        # résultat que si l'ORB, sur cette présélection embeddings, dépasse
        # nettement l'existant (mesuré : Ténéfix reverse-holo+watermark, ORB
        # 12 → 48 via l'embedding). On ne fait PAS confiance à la seule
        # similarité cosinus : sur le gold pur (ORB inexploitable), l'espace
        # d'embedding confond les cartes dorées entre elles (Zoroark→Sharpedo,
        # Garchomp→Flareon), et se fier au cosinus dégradait des cartes déjà
        # correctes. Le gold pur reste donc non résolu, mais sans faux positif.
        best_orb = best[0].orb_score if best else 0
        best_via_name = bool(best and "name" in best[0].matched_by)
        # Déclenchement : ORB franchement faible, OU match par PURE image (sans
        # indice de nom fiable) à ORB moyen — cas typique des full-arts.
        if best_orb < EMBED_FALLBACK_ORB or (not best_via_name and best_orb < EMBED_PURE_IMAGE_ORB):
            embedded = self._match_by_embedding(crop_image_bgr, EMBED_TOP_K)
            if embedded:
                reranked = _rerank_by_orb(crop_image_bgr, [_copy_candidate(c) for c in embedded])
                if reranked and reranked[0].orb_score > max(best_orb, EMBED_CONFIRM_MIN_ORB):
                    # Reverse-holo : l'illustration reste nette, l'ORB confirme.
                    for candidate in reranked:
                        candidate.matched_by = "embedding+image"
                    best = reranked
                else:
                    # Full-art : l'ORB ne confirme pas (illustration plein
                    # cadre), mais une similarité cosinus très haute et nettement
                    # en tête suffit (voir EMBED_COS_*). Le gold pur reste
                    # écarté (cosinus trop bas).
                    top = embedded[0]
                    runner_up = embedded[1].embed_sim if len(embedded) > 1 else 0.0
                    if top.embed_sim >= EMBED_COS_TRUST and top.embed_sim - runner_up >= EMBED_COS_MARGIN:
                        top.matched_by = "embedding"
                        best = [top]

        # Dernier recours pour la langue : sur une carte japonaise, l'OCR lit le
        # katakana trop approximativement pour que la correspondance exacte du
        # nom (plus haut) aboutisse — mais une fois la carte identifiée par
        # l'image, on peut confronter le texte au nom japonais de CETTE carte
        # seulement (voir `japanese_name_confirms`). Mesuré : Plusle AR et
        # Garchomp UR japonaises passent d'indéterminées à "Japonaise", sans
        # toucher aux cartes latines (aucun katakana à offrir).
        if effective_language is None and best:
            if japanese_name_confirms(text, best[0].name):
                effective_language = "Japonaise"

        return IdentificationResult(candidates=best[:top_k], language=effective_language)

    def identify_fast(self, crop_image_bgr: np.ndarray) -> IdentificationResult | None:
        """Identification par la seule image, sans OCR — ou `None` si le doute
        subsiste, auquel cas l'appelant repasse par `identify()`, inchangée.

        La langue d'impression n'est pas déterminée ici : elle ne se lit pas
        sur l'illustration, seulement dans le texte. L'appelant complète.
        """
        matrix, ids = _load_embedding_index()
        if matrix is None:
            return None
        vector = embed_image(crop_image_bgr)
        if vector is None:
            return None

        sims = matrix @ vector
        k = min(FAST_TOP_K, sims.shape[0])
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top])]

        candidates = []
        for i in top:
            row = self._row_by_id.get(ids[i])
            if row is None:
                continue
            candidates.append(
                MatchCandidate(
                    card_id=row["id"],
                    name=row["name"],
                    set_name=row["set_name"],
                    number=row["number"],
                    rarity=row["rarity"],
                    small_image_url=row["small_image_url"],
                    embed_sim=float(sims[i]),
                    matched_by="empreinte",
                )
            )
        if not candidates:
            return None

        reranked = _rerank_by_orb(crop_image_bgr, candidates)
        if not reranked or reranked[0].orb_score < FAST_MIN_ORB:
            return None
        # Un second candidat qui talonne le premier signale une illustration
        # partagée : l'image ne tranche pas, seul le texte le peut.
        runner_up = reranked[1].orb_score if len(reranked) > 1 else 0
        if reranked[0].orb_score - runner_up < FAST_MIN_ORB_MARGIN:
            return None
        return IdentificationResult(candidates=reranked, language=None)

    def _match_by_embedding(self, crop_image_bgr: np.ndarray, top_k: int) -> list[MatchCandidate]:
        """Présélection par similarité cosinus DINOv2 (meilleure des 4
        orientations du crop). Liste vide si l'index d'embeddings n'a pas
        encore été construit ou si le modèle est indisponible — on retombe
        alors proprement sur la voie pHash/ORB."""
        matrix, ids = _load_embedding_index()
        if matrix is None:
            return []
        vectors = embed_rotations(crop_image_bgr)  # [4, D]
        if vectors is None:
            return []
        # Similarité par carte = meilleure des 4 orientations (l'embedding
        # n'est pas invariant à la rotation ; gère les cartes BREAK pivotées).
        sims = (matrix @ vectors.T).max(axis=1)  # [N]
        k = min(top_k, sims.shape[0])
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top])]

        candidates = []
        for i in top:
            row = self._row_by_id.get(ids[i])
            if row is None:
                continue
            candidates.append(
                MatchCandidate(
                    card_id=row["id"],
                    name=row["name"],
                    set_name=row["set_name"],
                    number=row["number"],
                    rarity=row["rarity"],
                    small_image_url=row["small_image_url"],
                    embed_sim=float(sims[i]),
                )
            )
        return candidates

    def _match_by_image(self, image_bgr: np.ndarray, shortlist_size: int) -> list[MatchCandidate]:
        """Présélection pHash sur tout le cache puis reclassement ORB, sans
        indice OCR — la voie « pure image », utilisée aussi pour tester les
        orientations pivotées."""
        query_phash = compute_phash(image_bgr)
        shortlist = self._shortlist_by_phash(query_phash, top_k=shortlist_size)
        return _rerank_by_orb(image_bgr, shortlist)

    def _shortlist_by_hints(self, number: str | None, name_en: str | None) -> list[MatchCandidate]:
        target_number = None
        if number is not None:
            try:
                target_number = int(number)
            except ValueError:
                target_number = None

        if target_number is None and name_en is None:
            return []

        # Nom d'espèce cherché en BORNES DE MOT dans le nom de référence (pas
        # un simple préfixe) : le nom de la carte peut être suffixé ("Celebi-EX",
        # "Pikachu V") ET préfixé ("Team Rocket's Diglett", "Ash's Pikachu",
        # "M Charizard-EX"). Un préfixe seul ratait tous ces cas où l'espèce
        # n'est pas en tête (constaté : reverse-holo « Taupiqueur » lu
        # correctement mais exclu car la carte s'appelle « Team Rocket's
        # Diglett »). Les bornes gardent « Mew » distinct de « Mewtwo ».
        name_pattern = None
        if name_en is not None:
            name_pattern = re.compile(
                r"(?<![A-Za-z])" + re.escape(name_en) + r"(?![A-Za-z])", re.IGNORECASE
            )

        matches = []
        for row in self._rows:
            if target_number is not None:
                try:
                    if int(row["number"]) != target_number:
                        continue
                except (ValueError, TypeError):
                    continue
            if name_pattern is not None and not name_pattern.search(row["name"]):
                continue
            matches.append(
                MatchCandidate(
                    card_id=row["id"],
                    name=row["name"],
                    set_name=row["set_name"],
                    number=row["number"],
                    rarity=row["rarity"],
                    small_image_url=row["small_image_url"],
                )
            )
        return matches

    def _shortlist_by_phash(self, query_phash: str, top_k: int) -> list[MatchCandidate]:
        query_bits = _hex_to_bits(query_phash)
        distances = np.count_nonzero(self._bit_matrix != query_bits, axis=1)
        top_indices = np.argsort(distances, kind="stable")[:top_k]

        return [
            MatchCandidate(
                card_id=self._rows[i]["id"],
                name=self._rows[i]["name"],
                set_name=self._rows[i]["set_name"],
                number=self._rows[i]["number"],
                rarity=self._rows[i]["rarity"],
                small_image_url=self._rows[i]["small_image_url"],
                phash_distance=int(distances[i]),
            )
            for i in top_indices
        ]


def _is_confident_hint_match(reranked: list[MatchCandidate]) -> bool:
    top_score = reranked[0].orb_score
    if top_score >= NUMBER_HINT_MIN_ORB_SCORE:
        return True
    runner_up_score = reranked[1].orb_score if len(reranked) > 1 else 0
    return top_score >= NUMBER_HINT_MIN_ORB_SCORE_WITH_MARGIN and (
        runner_up_score == 0 or top_score >= NUMBER_HINT_MIN_MARGIN_RATIO * runner_up_score
    )


# Cache des descripteurs ORB des vignettes de référence : elles ne changent
# qu'à la resynchronisation du cache, et les recalculer à chaque reclassement
# (lecture disque + détection de points d'intérêt sur ~25 vignettes par carte
# à identifier) est le 2e poste de coût après l'OCR. `None` = vignette déjà
# tentée mais inexploitable (absente ou trop peu texturée), pour ne pas
# réessayer à chaque appel. Borné : ~16 Ko de descripteurs par carte, sans
# limite le cache pourrait atteindre ~320 Mo sur tout le catalogue — trop
# pour la VM. À la limite, on vide la moitié la plus ancienne (les dicts
# Python préservent l'ordre d'insertion).
_reference_descriptors_cache: dict[str, np.ndarray | None] = {}
MAX_CACHED_DESCRIPTORS = 4096


def _get_reference_descriptors(card_id: str, orb: cv2.ORB) -> np.ndarray | None:
    if card_id in _reference_descriptors_cache:
        return _reference_descriptors_cache[card_id]

    reference_path = REFERENCE_THUMBNAILS_DIR / f"{card_id}.jpg"
    reference_image = cv2.imread(str(reference_path))
    descriptors = None
    if reference_image is not None:
        _, descriptors = orb.detectAndCompute(reference_image, None)

    if len(_reference_descriptors_cache) >= MAX_CACHED_DESCRIPTORS:
        for stale_key in list(_reference_descriptors_cache)[: MAX_CACHED_DESCRIPTORS // 2]:
            del _reference_descriptors_cache[stale_key]

    _reference_descriptors_cache[card_id] = descriptors
    return descriptors


def _rerank_by_orb(crop_image_bgr: np.ndarray, candidates: list[MatchCandidate]) -> list[MatchCandidate]:
    if not candidates:
        return candidates

    orb = cv2.ORB_create(nfeatures=ORB_FEATURES)
    _, crop_descriptors = orb.detectAndCompute(crop_image_bgr, None)
    if crop_descriptors is None:
        return candidates  # image trop peu texturée pour l'ORB : on garde l'ordre pHash

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    for candidate in candidates:
        reference_descriptors = _get_reference_descriptors(candidate.card_id, orb)
        if reference_descriptors is None:
            continue

        matches = matcher.match(crop_descriptors, reference_descriptors)
        candidate.orb_score = sum(1 for m in matches if m.distance < ORB_GOOD_MATCH_MAX_DISTANCE)

    return sorted(candidates, key=lambda c: c.orb_score, reverse=True)


def _hex_to_bits(hex_hash: str) -> np.ndarray:
    as_int = int(hex_hash, 16)
    bits = [(as_int >> i) & 1 for i in range(HASH_BITS - 1, -1, -1)]
    return np.array(bits, dtype=np.uint8)


# Index mis en cache entre les requêtes : recharger 20 000+ lignes et
# reconstruire la matrice de bits à chaque identification coûtait plus d'une
# seconde par requête pour des données qui ne changent qu'à la
# resynchronisation. Invalidé par la date de modification du fichier SQLite.
_index_cache: ReferenceIndex | None = None
_index_cache_db_mtime: float | None = None


def load_reference_index() -> ReferenceIndex:
    global _index_cache, _index_cache_db_mtime

    try:
        db_mtime = SQLITE_PATH.stat().st_mtime
    except OSError:
        db_mtime = None
    if _index_cache is not None and db_mtime == _index_cache_db_mtime:
        return _index_cache

    with db_cursor() as cursor:
        cursor.execute(
            "SELECT id, name, set_name, number, rarity, small_image_url, phash FROM reference_cards"
        )
        rows = [dict(row) for row in cursor.fetchall()]

    if not rows:
        index = ReferenceIndex(rows=[], bit_matrix=np.zeros((0, HASH_BITS), dtype=np.uint8))
    else:
        bit_matrix = np.stack([_hex_to_bits(row["phash"]) for row in rows])
        index = ReferenceIndex(rows=rows, bit_matrix=bit_matrix)

    _index_cache = index
    _index_cache_db_mtime = db_mtime
    return index


def _copy_candidate(candidate: MatchCandidate) -> MatchCandidate:
    return replace(candidate)


# Index d'embeddings mis en cache (matrice [N, D] + ids alignés), invalidé par
# la date de modification du fichier .npy. Construit par
# app.scripts.build_card_embeddings ; absent tant que ce script n'a pas tourné,
# auquel cas le repli embeddings reste simplement inactif.
EMBEDDINGS_PATH = DB_DIR / "card_embeddings.npy"
EMBEDDINGS_IDS_PATH = DB_DIR / "card_embeddings_ids.json"
_embedding_cache: tuple[np.ndarray, list[str]] | None = None
_embedding_cache_mtime: float | None = None


def _load_embedding_index() -> tuple[np.ndarray | None, list[str] | None]:
    global _embedding_cache, _embedding_cache_mtime
    try:
        mtime = EMBEDDINGS_PATH.stat().st_mtime
    except OSError:
        return None, None
    if _embedding_cache is not None and mtime == _embedding_cache_mtime:
        return _embedding_cache
    try:
        matrix = np.load(EMBEDDINGS_PATH).astype(np.float32)
        ids = json.loads(EMBEDDINGS_IDS_PATH.read_text())
        if len(ids) != len(matrix):
            return None, None
    except Exception:
        return None, None
    _embedding_cache = (matrix, ids)
    _embedding_cache_mtime = mtime
    return _embedding_cache
