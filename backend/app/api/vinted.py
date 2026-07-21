"""Aide à la saisie sur Vinted — PAS un bot.

Vinted interdit l'automatisation de la publication ; ici rien n'est publié ni
soumis automatiquement. Le flux est entièrement déclenché par l'utilisateur :

1. Dans Splitdex, bouton "Envoyer vers Vinted" sur une fiche → la fiche
   (titre, description, prix, état) est simplement mémorisée ici comme
   "dernière fiche préparée" (en mémoire, rien de persisté).
2. Sur la page "Vendre" de Vinted, ouverte manuellement dans le navigateur,
   un userscript Tampermonkey affiche un bouton : au clic, il récupère cette
   fiche et remplit les champs du formulaire — l'équivalent d'un
   copier-coller multi-champs, étendu aux menus déroulants fixes (catégorie
   "Cartes à collectionner", marque "Pokémon", état) en simulant les clics
   qu'aurait faits l'utilisateur.
3. L'utilisateur relit, ajoute les photos, et clique lui-même sur "Ajouter".
   Aucune action n'est effectuée sans son clic.

Architecture en deux morceaux (leçon des itérations de débogage : chaque
correctif exigeait une réinstallation Tampermonkey, souvent contournée par le
cache) :
- `/vinted-autofill.user.js` : **lanceur** minimal installé une seule fois
  dans Tampermonkey — il affiche le bouton et, à chaque clic, télécharge et
  exécute la logique fraîche depuis le serveur.
- `/vinted-autofill-core.js` : la **logique de remplissage**, servie avec
  `Cache-Control: no-store` + cache-buster — modifiable côté serveur sans
  jamais retoucher l'installation Tampermonkey.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

router = APIRouter(tags=["vinted"])

# Dernière fiche "envoyée vers Vinted" depuis l'UI. En mémoire uniquement :
# c'est un tampon d'échange entre deux onglets du même utilisateur, pas une
# donnée à conserver (perdue au redémarrage du serveur, sans conséquence).
_staged_listing: dict | None = None


class StagedListing(BaseModel):
    title: str
    description: str
    price: float | None = None
    condition: str | None = None


@router.post("/api/vinted/staged")
async def stage_listing(listing: StagedListing):
    global _staged_listing
    _staged_listing = listing.model_dump()
    return {"status": "ok"}


@router.get("/api/vinted/staged")
async def get_staged_listing():
    if _staged_listing is None:
        raise HTTPException(
            status_code=404,
            detail="Aucune fiche préparée — clique d'abord sur « Envoyer vers Vinted » dans Splitdex.",
        )
    return _staged_listing


LOADER_TEMPLATE = """\
// ==UserScript==
// @name         Splitdex → Vinted (remplissage du formulaire)
// @namespace    splitdex
// @version      2.0
// @description  Bouton "Remplir depuis Splitdex" sur la page Vendre de Vinted. La logique de remplissage est téléchargée fraîche depuis le serveur Splitdex à chaque clic (aucune réinstallation lors des mises à jour). Aucune publication automatique.
// @match        https://www.vinted.fr/items/new*
// @match        https://www.vinted.fr/*/items/new*
// @grant        GM_xmlhttpRequest
// @connect      __SPLITDEX_HOSTNAME__
// ==/UserScript==

(function () {
  "use strict";

  const SPLITDEX_ORIGIN = "__SPLITDEX_ORIGIN__";

  function showError(message) {
    const toast = document.createElement("div");
    toast.textContent = message;
    Object.assign(toast.style, {
      position: "fixed", bottom: "80px", right: "20px", zIndex: 99999,
      background: "#b91c1c", color: "white", padding: "10px 16px",
      borderRadius: "8px", fontSize: "14px", maxWidth: "340px",
      boxShadow: "0 4px 12px rgba(0,0,0,0.25)",
    });
    document.body.append(toast);
    setTimeout(() => toast.remove(), 8000);
  }

  const button = document.createElement("button");
  button.textContent = "📋 Remplir depuis Splitdex";
  Object.assign(button.style, {
    position: "fixed", bottom: "20px", right: "20px", zIndex: 99999,
    background: "#0f766e", color: "white", border: "none",
    borderRadius: "999px", padding: "12px 18px", fontSize: "14px",
    fontWeight: "600", cursor: "pointer",
    boxShadow: "0 4px 12px rgba(0,0,0,0.25)",
  });
  button.addEventListener("click", () => {
    button.disabled = true;
    GM_xmlhttpRequest({
      method: "GET",
      // cache-buster : toujours la dernière version de la logique
      url: SPLITDEX_ORIGIN + "/vinted-autofill-core.js?ts=" + Date.now(),
      onload: function (response) {
        button.disabled = false;
        if (response.status !== 200) {
          showError("Splitdex — impossible de charger la logique (HTTP " + response.status + ")");
          return;
        }
        try {
          // Exécuté dans le bac à sable du userscript : GM_xmlhttpRequest
          // reste accessible à la logique téléchargée.
          eval(response.responseText);
        } catch (e) {
          showError("Splitdex — erreur dans la logique : " + e.message);
          console.error("[Splitdex]", e);
        }
      },
      onerror: function () {
        button.disabled = false;
        showError("Splitdex injoignable (" + SPLITDEX_ORIGIN + ") — serveur lancé ? même réseau ?");
      },
    });
  });
  document.body.append(button);
})();
"""


CORE_VERSION = "2.4"

CORE_TEMPLATE = """\
(function () {
  "use strict";

  const SPLITDEX_ORIGIN = "__SPLITDEX_ORIGIN__";
  const CORE_VERSION = "__CORE_VERSION__";

  function debugLog() {
    console.log.apply(console, ["[Splitdex core v" + CORE_VERSION + "]"].concat(Array.from(arguments)));
  }
  debugLog("logique chargée");

  // Vinted est une application React : assigner input.value directement ne
  // met pas à jour son état interne. Il faut passer par le setter natif du
  // prototype puis émettre un événement input, comme le ferait une frappe.
  function setNativeValue(element, value) {
    const prototype =
      element instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value").set;
    setter.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function simulateClick(element) {
    for (const type of ["pointerdown", "mousedown", "pointerup", "mouseup", "click"]) {
      element.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true }));
    }
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function waitFor(predicate, timeoutMs) {
    return new Promise((resolve) => {
      const startedAt = Date.now();
      const timer = setInterval(() => {
        const result = predicate();
        if (result) {
          clearInterval(timer);
          resolve(result);
        } else if (Date.now() - startedAt > timeoutMs) {
          clearInterval(timer);
          resolve(null);
        }
      }, 120);
    });
  }

  const FIELD_SELECTORS = {
    title: ['input[name="title"]', '[data-testid="title--input"]', "input#title"],
    description: [
      'textarea[name="description"]',
      '[data-testid="description--input"]',
      "textarea#description",
    ],
    price: ['input[name="price"]', '[data-testid="price-input--input"]', "input#price"],
    category: [
      '[data-testid="catalog-select-dropdown-input"]',
      '[data-testid*="catalog"] input',
      'input[name="category"]',
    ],
    brand: [
      '[data-testid="brand-select-dropdown-input"]',
      '[data-testid*="brand"] input',
      'input[name="brand"]',
    ],
    condition: [
      '[data-testid="condition-select-dropdown-input"]',
      'input[data-testid*="condition"]',
      'input[data-testid*="status"]',
      '[data-testid*="condition"] input',
      '[data-testid*="status"] input',
      'input[name="status"]',
      'input[name="condition"]',
      // Même convention que la catégorie ("Sélectionne une catégorie").
      'input[placeholder*="état" i]',
    ],
  };

  function findField(selectors) {
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el) return el;
    }
    return null;
  }

  // Entrées des menus Vinted : cellules web_ui (relevé réel du markup,
  // 2026-07) — le libellé est dans un span .web_ui__Cell__title, le clic
  // doit viser la cellule .web_ui__Cell__cell parente quand elle existe.
  function visibleCells() {
    return Array.from(
      document.querySelectorAll('.web_ui__Cell__title, .web_ui__Cell__cell, [role="option"]')
    ).filter((el) => el.offsetParent !== null);
  }

  function cellTexts() {
    return visibleCells().map((el) => (el.textContent || "").trim());
  }

  // Détecteur d'ouverture de panneau fiable : la page "Vendre" contient déjà
  // des éléments Cell (zone photos, "Prix", mentions légales...) — on compare
  // donc avec un instantané des textes visibles AVANT le clic : le panneau
  // est ouvert quand suffisamment de NOUVELLES entrées sont apparues.
  function makePanelOpenDetector(minNewCells) {
    const baseline = new Set(cellTexts());
    return () => {
      const fresh = cellTexts().filter((text) => text && !baseline.has(text));
      return fresh.length >= minNewCells;
    };
  }

  function findCellByText(pattern, alreadyClicked) {
    const label = visibleCells().find((el) => {
      const text = (el.textContent || "").trim();
      if (!(text.length > 0 && text.length < 80 && pattern.test(text))) return false;
      const clickable = el.closest(".web_ui__Cell__cell") || el;
      return !(alreadyClicked && alreadyClicked.has(clickable));
    });
    if (!label) return null;
    return label.closest(".web_ui__Cell__cell") || label;
  }

  async function openDropdown(trigger, isOpen, fieldLabel) {
    if (isOpen()) {
      debugLog(fieldLabel, ": panneau déjà ouvert avant toute tentative (suspect)");
      return true;
    }
    const attempts = [
      ["click natif", () => trigger.click()],
      ["focus + click", () => { trigger.focus(); trigger.click(); }],
      ["séquence pointer/mouse", () => simulateClick(trigger)],
      ["clic sur le chevron", () => {
        const scope = trigger.closest("div") || document;
        const chevron = scope.querySelector('[data-testid*="chevron"]');
        if (chevron) simulateClick(chevron);
      }],
      ["clic sur le parent", () => {
        if (trigger.parentElement) simulateClick(trigger.parentElement);
      }],
    ];
    for (const [label, attempt] of attempts) {
      attempt();
      const opened = await waitFor(isOpen, 1200);
      if (opened) {
        debugLog(fieldLabel, ": menu ouvert via :", label);
        return true;
      }
      debugLog(fieldLabel, ": échec ouverture via :", label);
    }
    // Dernier recours : certains composants n'acceptent que les vrais clics
    // utilisateur (event.isTrusted) — on demande le clic à l'utilisateur et
    // on reprend la navigation automatiquement dès que le panneau s'ouvre.
    showToast(
      "Impossible d'ouvrir le menu « " + fieldLabel + " » automatiquement.\\n" +
      "👉 Clique toi-même sur ce champ, je continue dès qu'il s'ouvre (20s).",
      true
    );
    const opened = await waitFor(isOpen, 20000);
    if (opened) {
      debugLog(fieldLabel, ": menu ouvert manuellement par l'utilisateur");
      return true;
    }
    debugLog(fieldLabel, ": menu jamais ouvert");
    return false;
  }

  // Cible exacte (relevé réel de l'arborescence Vinted, 2026-07) :
  // Loisirs et collections > Cartes à collectionner > Cartes à collectionner
  // à l'unité. Motifs ancrés (^...$) : un motif flou matcherait aussi "Lots
  // de cartes à collectionner" (constaté : la feuille correcte avait été
  // cliquée puis écrasée par ce faux frère). L'apostrophe peut être droite
  // ou typographique selon le rendu.
  const CATEGORY_LEAF_PATTERN = /^cartes à collectionner à l['\\u2019]unité$/i;
  const CATEGORY_STEP_PATTERNS = [
    CATEGORY_LEAF_PATTERN,
    /^cartes à collectionner$/i,
    /^loisirs et collections$/i,
    /^collections?$/i,
    /^divertissement$/i,
  ];

  async function selectCategory() {
    const trigger = findField(FIELD_SELECTORS.category);
    if (!trigger) {
      debugLog("catégorie : champ déclencheur introuvable");
      return false;
    }

    // Le 1er niveau du menu apporte ~8 nouvelles entrées (Femmes, Hommes...).
    const panelIsOpen = makePanelOpenDetector(4);
    if (!(await openDropdown(trigger, panelIsOpen, "Catégorie"))) {
      return false;
    }

    const alreadyClicked = new Set();
    let leafClicked = false;
    for (let step = 0; step < 6; step++) {
      const cell = await waitFor(() => {
        for (const pattern of CATEGORY_STEP_PATTERNS) {
          const found = findCellByText(pattern, alreadyClicked);
          if (found) return found;
        }
        return null;
      }, step === 0 ? 4000 : 1500);
      if (!cell) {
        debugLog("catégorie : plus d'entrée correspondante au niveau", step, "- entrées visibles :",
          visibleCells().slice(0, 15).map((c) => (c.textContent || "").trim()).join(" | "));
        break;
      }
      const cellText = (cell.textContent || "").trim();
      debugLog("catégorie : clic sur «", cellText, "»");
      alreadyClicked.add(cell);
      simulateClick(cell);
      await sleep(600);
      if (CATEGORY_LEAF_PATTERN.test(cellText)) {
        // Feuille cible atteinte : surtout ne pas continuer la boucle, le
        // niveau reste affiché et un autre libellé proche serait cliqué
        // par-dessus la bonne sélection.
        leafClicked = true;
        break;
      }
    }

    // Certains panneaux exigent une validation explicite pour fermer et
    // reporter la sélection dans le champ (bouton "Fait" constaté).
    const doneButton = Array.from(document.querySelectorAll("button")).find(
      (b) => b.offsetParent !== null && /^(fait|terminé|valider)$/i.test((b.textContent || "").trim())
    );
    if (doneButton) {
      debugLog("catégorie : clic sur le bouton de validation «", (doneButton.textContent || "").trim(), "»");
      simulateClick(doneButton);
    }

    const filled = await waitFor(() => trigger.value.trim().length > 0, 3000);
    debugLog("catégorie : feuille cliquée =", leafClicked, "; valeur finale du champ = «", trigger.value, "»");
    return leafClicked && filled !== null;
  }

  async function selectBrand() {
    // Le champ marque n'existe qu'une fois la catégorie choisie (relevé
    // réel : absent du formulaire initial) — on attend son apparition.
    const trigger = await waitFor(() => findField(FIELD_SELECTORS.brand), 5000);
    if (!trigger) {
      debugLog("marque : champ introuvable (la catégorie est-elle bien sélectionnée ?)");
      return false;
    }

    const newCellsAppeared = makePanelOpenDetector(1);
    // Attention : le champ marque lui-même a un placeholder contenant
    // "marque" — l'exclure du test, sinon le menu est cru ouvert d'office
    // (constaté : "panneau déjà ouvert (suspect)" et rien ne se remplissait).
    const panelIsOpen = () => {
      if (newCellsAppeared()) return true;
      const search = document.querySelector('input[placeholder*="marque" i], input[type="search"]');
      return search !== null && search !== trigger;
    };
    if (!(await openDropdown(trigger, panelIsOpen, "Marque"))) {
      return false;
    }

    if (trigger.tagName === "INPUT") {
      setNativeValue(trigger, "Pokémon");
    } else {
      const search = document.querySelector('input[placeholder*="marque" i], input[type="search"]');
      if (search) setNativeValue(search, "Pokémon");
    }

    const cell = await waitFor(() => findCellByText(/^pok[ée]mon$/i, null), 4000);
    if (!cell) {
      debugLog("marque : entrée « Pokémon » introuvable - entrées visibles :",
        visibleCells().slice(0, 10).map((c) => (c.textContent || "").trim()).join(" | "));
      return false;
    }
    debugLog("marque : clic sur «", (cell.textContent || "").trim(), "»");
    simulateClick(cell);
    await sleep(300);
    return true;
  }

  // Vocabulaire Splitdex → libellés exacts des états Vinted. "Neuf" côté
  // cartes correspond à "Neuf sans étiquette" côté Vinted.
  const CONDITION_PATTERNS = {
    "Neuf": /^neuf sans étiquette$/i,
    "Très bon état": /^très bon état$/i,
    "Bon état": /^bon état$/i,
    "Satisfaisant": /^satisfaisant$/i,
  };

  async function selectCondition(conditionLabel) {
    const pattern = CONDITION_PATTERNS[conditionLabel];
    if (!pattern) return false;
    const trigger = await waitFor(() => findField(FIELD_SELECTORS.condition), 5000);
    if (!trigger) {
      // Diagnostic : liste les champs réellement présents pour ajuster les
      // sélecteurs à la prochaine itération.
      debugLog("état : champ introuvable - inputs présents :",
        Array.from(document.querySelectorAll("input"))
          .map((i) => (i.getAttribute("data-testid") || i.name || i.placeholder || "?"))
          .filter((s) => s !== "?")
          .join(" | "));
      return false;
    }

    if (!(await openDropdown(trigger, () => findCellByText(pattern, null) !== null, "État"))) {
      debugLog("état : entrées visibles :",
        visibleCells().slice(0, 10).map((c) => (c.textContent || "").trim()).join(" | "));
      return false;
    }
    const cell = findCellByText(pattern, null);
    if (!cell) return false;
    debugLog("état : clic sur «", (cell.textContent || "").trim(), "»");
    simulateClick(cell);
    await sleep(300);
    return true;
  }

  function showToast(message, isError) {
    const toast = document.createElement("div");
    toast.textContent = message;
    Object.assign(toast.style, {
      position: "fixed",
      bottom: "80px",
      right: "20px",
      zIndex: 99999,
      background: isError ? "#b91c1c" : "#166534",
      color: "white",
      padding: "10px 16px",
      borderRadius: "8px",
      fontSize: "14px",
      maxWidth: "340px",
      whiteSpace: "pre-line",
      boxShadow: "0 4px 12px rgba(0,0,0,0.25)",
    });
    document.body.append(toast);
    setTimeout(() => toast.remove(), 10000);
  }

  function formatPrice(price) {
    if (price == null) return null;
    return String(price).replace(".", ",");
  }

  // Taille du colis : toujours "Petit" pour une carte. Les options
  // Petit/Moyen/Grand sont des cellules directement sur la page (pas un
  // menu), elles apparaissent après le choix de la catégorie (relevé réel).
  async function selectPackageSize() {
    const cell = await waitFor(() => findCellByText(/^petit$/i, null), 5000);
    if (!cell) {
      debugLog("taille du colis : option « Petit » introuvable");
      return false;
    }
    debugLog("taille du colis : clic sur « Petit »");
    simulateClick(cell);
    await sleep(300);
    return true;
  }

  async function fillForm(listing) {
    const filled = [];
    const missing = [];

    // Titre et description d'abord (indépendants du reste)...
    const titleField = findField(FIELD_SELECTORS.title);
    if (titleField) {
      setNativeValue(titleField, listing.title);
      filled.push("titre");
    } else missing.push("titre");

    const descriptionField = findField(FIELD_SELECTORS.description);
    if (descriptionField) {
      setNativeValue(descriptionField, listing.description);
      filled.push("description");
    } else missing.push("description");

    // ...puis les menus, dans l'ordre imposé par Vinted (marque/état/colis
    // n'apparaissent qu'après le choix de la catégorie)...
    if (await selectCategory()) filled.push("catégorie");
    else missing.push("catégorie");

    if (await selectBrand()) filled.push("marque");
    else missing.push("marque");

    if (listing.condition) {
      if (await selectCondition(listing.condition)) filled.push("état (" + listing.condition + ")");
      else missing.push("état");
    }

    if (await selectPackageSize()) filled.push("taille du colis (Petit)");
    else missing.push("taille du colis");

    // ...et le prix EN DERNIER : la sélection de la catégorie fait
    // ré-afficher le formulaire et effaçait un prix rempli trop tôt
    // (constaté en pratique).
    const price = formatPrice(listing.price);
    if (price !== null) {
      const priceField = await waitFor(() => findField(FIELD_SELECTORS.price), 3000);
      if (priceField) {
        setNativeValue(priceField, price);
        filled.push("prix");
      } else missing.push("prix");
    }

    // Filet de sécurité : si les ré-affichages du formulaire ont vidé le
    // titre ou la description, on les re-remplit.
    const titleAgain = findField(FIELD_SELECTORS.title);
    if (titleAgain && !titleAgain.value.trim()) setNativeValue(titleAgain, listing.title);
    const descriptionAgain = findField(FIELD_SELECTORS.description);
    if (descriptionAgain && !descriptionAgain.value.trim()) setNativeValue(descriptionAgain, listing.description);

    let message = "Splitdex — rempli : " + (filled.join(", ") || "rien") + ".";
    if (missing.length) {
      message += "\\nÀ finir à la main : " + missing.join(", ") + ".";
    }
    message += "\\nReste : photos, puis relecture avant d'ajouter.";
    showToast(message, missing.length > 0);
  }

  GM_xmlhttpRequest({
    method: "GET",
    url: SPLITDEX_ORIGIN + "/api/vinted/staged",
    onload: function (response) {
      if (response.status === 200) {
        fillForm(JSON.parse(response.responseText));
      } else {
        let detail = "Erreur " + response.status;
        try {
          detail = JSON.parse(response.responseText).detail || detail;
        } catch (e) {}
        showToast("Splitdex — " + detail, true);
      }
    },
    onerror: function () {
      showToast("Splitdex injoignable (" + SPLITDEX_ORIGIN + ")", true);
    },
  });
})();
"""

NO_STORE_HEADERS = {"Cache-Control": "no-store, max-age=0"}


def _origin_and_hostname(request: Request) -> tuple[str, str]:
    host = request.headers.get("host", "localhost:8000")
    return f"http://{host}", host.split(":")[0]


@router.get("/vinted-autofill.user.js", response_class=PlainTextResponse)
async def userscript_loader(request: Request):
    """Lanceur Tampermonkey (à installer une seule fois) — l'adresse du
    serveur est injectée dynamiquement selon l'hôte par lequel le navigateur
    nous joint (IP LAN sur la VM, localhost plus tard sur le Mac)."""
    origin, hostname = _origin_and_hostname(request)
    script = LOADER_TEMPLATE.replace("__SPLITDEX_ORIGIN__", origin).replace(
        "__SPLITDEX_HOSTNAME__", hostname
    )
    return PlainTextResponse(script, media_type="text/javascript; charset=utf-8", headers=NO_STORE_HEADERS)


@router.get("/vinted-autofill-core.js", response_class=PlainTextResponse)
async def userscript_core(request: Request):
    """Logique de remplissage, rechargée fraîche à chaque clic du bouton."""
    origin, _ = _origin_and_hostname(request)
    script = CORE_TEMPLATE.replace("__SPLITDEX_ORIGIN__", origin).replace(
        "__CORE_VERSION__", CORE_VERSION
    )
    return PlainTextResponse(script, media_type="text/javascript; charset=utf-8", headers=NO_STORE_HEADERS)
