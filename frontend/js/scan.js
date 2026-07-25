import * as api from "./api.js";
import { getSession, updateSession, createSession } from "./session-store.js";
import { el, formatDate, copyToClipboard, mountNav, MAX_PHOTOS_PER_BATCH, LANGUAGE_FLAGS, LANGUAGE_OPTIONS } from "./common.js";

mountNav(null);

const params = new URLSearchParams(location.search);
const sessionId = params.get("s");
const session = sessionId ? getSession(sessionId) : null;
const root = document.getElementById("session-root");

let conditions = ["Très bon état"];
let processing = false;
let cancelRequested = false;
let scanAbort = null; // AbortController du scan en cours (pour l'annulation)

/* Registre des blocs-carte, clé `${photoId}|${filename}` → CardBlock. */
const blocks = new Map();
/* Suivi par photo : { crops, identified:bool, listed:bool }. */
const photoState = new Map();

if (!session) {
  renderMissing();
} else {
  init();
}

function renderMissing() {
  root.append(
    el("div", { class: "clay empty-state" }, [
      el("h2", { text: "Session introuvable" }),
      el("p", { text: "Cette session de scan n'existe plus dans ce navigateur. Lancez-en une nouvelle depuis l'accueil." }),
      el("a", { class: "btn btn-primary", attrs: { href: "/" }, text: "Retour à l'accueil", }),
    ])
  );
}

/* ── En-tête + squelette ──────────────────────────────────────────────── */
let headerEls;

async function init() {
  try {
    conditions = await api.getConditions();
  } catch { /* défaut conservé */ }

  headerEls = renderHeader();
  const grid = el("div", { class: "cards-grid", attrs: { id: "cards-grid" } });
  root.append(grid);

  // 1. Charger/assurer les crops de chaque photo et bâtir les blocs.
  for (let i = 0; i < session.photoIds.length; i++) {
    const photoId = session.photoIds[i];
    let crops = [];
    try {
      crops = await api.getCrops(photoId);
      if (!crops.length) crops = await api.runCrops(photoId);
    } catch { crops = []; }
    photoState.set(photoId, { crops, identified: false, listed: false });
    appendPhotoCards(grid, photoId, i, crops);
  }

  // 2. Restaurer l'état déjà calculé (revisite d'une session).
  for (const photoId of session.photoIds) {
    try {
      const idents = await api.getIdentifications(photoId);
      if (idents.length) {
        photoState.get(photoId).identified = true;
        for (const ident of idents) applyIdentification(photoId, ident);
      }
      const listings = await api.getListings(photoId);
      if (listings.length) {
        photoState.get(photoId).listed = true;
        for (const listing of listings) applyListing(photoId, listing);
      }
    } catch { /* rien à restaurer */ }
  }

  // 3. Traiter automatiquement les photos pas encore abouties.
  const pending = session.photoIds.filter((id) => !photoState.get(id).listed);
  if (pending.length) {
    await processPhotos(pending);
  } else {
    updateSessionSummary();
  }
  // Toute carte encore « en cours » sans fiche (photo sans détection, échec…)
  // arrête de tourner.
  for (const block of blocks.values()) if (!block.hasListing()) block.setLoading(false);
}

function clearLoadingForPhoto(photoId) {
  const state = photoState.get(photoId);
  for (const crop of state.crops) {
    const block = blocks.get(`${photoId}|${crop.filename}`);
    if (block && !block.hasListing()) block.setLoading(false);
  }
}

function renderHeader() {
  const total = session.photoIds.length;
  const procLabel = el("span", { text: "" });
  const procFill = el("div", { class: "fill" });
  const procBar = el("div", { class: "progress" }, [procFill]);
  const stopBtn = el("button", {
    class: "btn btn-sm btn-stop",
    text: "Arrêter",
    attrs: { title: "Interrompre le scan en cours" },
    on: { click: cancelScan },
  });
  const procWrap = el("div", { class: "proc hidden" }, [
    el("div", { class: "lbl" }, [el("div", { class: "spinner" }), procLabel, stopBtn]),
    procBar,
  ]);

  // Nouveau scan : sélecteur de fichiers caché déclenché depuis la barre
  // d'actions, sans repasser par l'accueil.
  const newInput = el("input", { attrs: { type: "file", accept: "image/jpeg,image/png,image/webp", multiple: "", hidden: "" } });
  newInput.addEventListener("change", () => startNewScan(newInput.files, newScanBtn));
  const newScanBtn = el("button", {
    class: "btn btn-primary btn-sm",
    text: "＋ Nouveau scan",
    on: { click: () => newInput.click() },
  });
  const reprocessBtn = el("button", {
    class: "btn btn-sm",
    text: "Tout retraiter",
    on: { click: () => processPhotos(session.photoIds, true) },
  });
  const exportBtn = el("button", {
    class: "btn btn-sm",
    text: "Exporter (ZIP)",
    on: { click: exportAll },
  });

  const head = el("div", { class: "clay session-head" }, [
    el("div", { class: "top" }, [
      el("div", {}, [
        el("h1", { text: "Session de scan" }),
        el("div", { class: "sub", text: `${formatDate(session.createdAt)} · ${total} photo${total > 1 ? "s" : ""}` }),
      ]),
      el("div", { class: "actions" }, [newScanBtn, reprocessBtn, exportBtn, newInput]),
    ]),
    procWrap,
  ]);
  root.append(head);
  return { procWrap, procBar, procLabel, procFill, reprocessBtn, exportBtn, stopBtn };
}

// Interrompt le scan en cours : coupe la requête réseau en vol et empêche le
// lancement des photos suivantes. Le nettoyage est fait par le `finally` de
// processPhotos.
function cancelScan() {
  if (!processing) return;
  cancelRequested = true;
  scanAbort?.abort();
  headerEls.stopBtn.disabled = true;
  headerEls.procLabel.textContent = "Arrêt du scan…";
}

async function startNewScan(fileList, button) {
  const files = Array.from(fileList).filter((f) => f.type.startsWith("image/"));
  if (!files.length) return;
  if (files.length > MAX_PHOTOS_PER_BATCH) {
    alert(`Trop de photos (${files.length}) : maximum ${MAX_PHOTOS_PER_BATCH} par session.`);
    return;
  }
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Envoi…";
  try {
    const { photos } = await api.uploadPhotos(files);
    const newSession = createSession(photos);
    window.location.href = `/scan?s=${newSession.id}`;
  } catch (err) {
    alert(`Erreur : ${err.message}`);
    button.disabled = false;
    button.textContent = original;
  }
}

// Cartes de toutes les photos dans la grille PARTAGÉE : des photos
// individuelles (1 carte chacune) flottent côte à côte au lieu de s'empiler.
// Un séparateur pleine largeur n'apparaît que pour une planche (lot de
// plusieurs cartes), pour garder le repère de regroupement.
function appendPhotoCards(grid, photoId, index, crops) {
  if (crops.length > 1) {
    const cover = session.photoUrls?.[photoId] ?? (index === 0 ? session.coverUrl : null) ?? `/uploads/${photoId}.jpg`;
    grid.append(el("div", { class: "lot-divider" }, [
      el("img", { attrs: { src: cover, alt: "", onerror: "this.style.visibility='hidden'" } }),
      el("div", { class: "t", text: `Photo ${index + 1}` }),
      el("span", { class: "muted", text: `${crops.length} cartes`, attrs: { style: "font-weight:700;font-size:13px" } }),
    ]));
  }
  if (!crops.length) {
    grid.append(el("div", { class: "empty-photo", text: `Photo ${index + 1} : aucune carte détectée — vérifie l'éclairage et le fond.` }));
    return;
  }
  for (const crop of crops) {
    const block = makeCardBlock(photoId, crop);
    blocks.set(`${photoId}|${crop.filename}`, block);
    grid.append(block.el);
  }
}

/* ── Traitement (identification + génération) ─────────────────────────── */
async function processPhotos(photoIds, force = false) {
  if (processing) return;
  processing = true;
  cancelRequested = false;
  scanAbort = new AbortController();
  headerEls.reprocessBtn.disabled = true;
  headerEls.stopBtn.disabled = false;
  headerEls.procWrap.classList.remove("hidden");
  headerEls.procBar.classList.add("indet"); // animation continue tant que ça scanne

  const targets = force ? photoIds : photoIds.filter((id) => !photoState.get(id).listed);
  const totalCards = targets.reduce((n, id) => n + photoState.get(id).crops.length, 0);
  let cardsDone = 0;
  let stopped = false;
  try {
    for (let i = 0; i < targets.length; i++) {
      if (cancelRequested) { stopped = true; break; }
      const photoId = targets[i];
      const state = photoState.get(photoId);
      const photoInfo = targets.length > 1 ? ` · photo ${i + 1}/${targets.length}` : "";
      headerEls.procLabel.textContent = `Scan des cartes en cours… ${cardsDone}/${totalCards}${photoInfo}`;
      // Les cartes de cette photo passent (ou restent) en « scan en cours ».
      for (const crop of state.crops) blocks.get(`${photoId}|${crop.filename}`)?.setLoading(true);
      try {
        if (force || !state.identified) {
          const idents = await api.runIdentify(photoId, scanAbort.signal);
          state.identified = true;
          for (const ident of idents) applyIdentification(photoId, ident);
        }
        const listings = await api.generateListings(photoId, scanAbort.signal);
        state.listed = true;
        for (const listing of listings) applyListing(photoId, listing);
      } catch (err) {
        if (err.name === "AbortError" || cancelRequested) { stopped = true; break; }
        console.error("Traitement photo échoué", photoId, err);
      }
      clearLoadingForPhoto(photoId);
      cardsDone += state.crops.length;
      headerEls.procLabel.textContent = `Scan des cartes en cours… ${cardsDone}/${totalCards}`;
    }
  } finally {
    // Coupe les spinners des cartes non abouties (photos restantes ou scan
    // interrompu en plein milieu).
    for (const block of blocks.values()) if (!block.hasListing()) block.setLoading(false);
    headerEls.procBar.classList.remove("indet");
    headerEls.procWrap.classList.add("hidden");
    headerEls.reprocessBtn.disabled = false;
    headerEls.stopBtn.disabled = false;
    scanAbort = null;
    processing = false;
    updateSessionSummary();
    if (stopped) {
      headerEls.procLabel.textContent = "";
    }
  }
}

function applyIdentification(photoId, ident) {
  const block = blocks.get(`${photoId}|${ident.crop_filename}`);
  if (block) block.setIdentification(ident);
}
function applyListing(photoId, listing) {
  const block = blocks.get(`${photoId}|${listing.crop_filename}`);
  if (block) block.setListing(listing);
}

/* Résumé de session (pour l'accueil + l'historique). */
function updateSessionSummary() {
  let cardCount = 0;
  const languages = {};
  for (const block of blocks.values()) {
    const lang = block.currentLanguage();
    if (block.hasCard()) {
      cardCount++;
      if (lang) languages[lang] = (languages[lang] || 0) + 1;
    }
  }
  updateSession(session.id, { cardCount, languages });
}

async function exportAll() {
  for (const photoId of session.photoIds) {
    const link = el("a", { attrs: { href: api.exportUrl(photoId), download: `splitdex_${photoId}.zip` } });
    document.body.append(link);
    link.click();
    link.remove();
    await new Promise((r) => setTimeout(r, 400)); // laisse le navigateur enchaîner les téléchargements
  }
}

/* ── Bloc-carte ───────────────────────────────────────────────────────── */
function makeCardBlock(photoId, crop) {
  const container = el("div", { class: "clay card-block" });
  let identification = null;
  let listing = null;
  let loading = true; // dès la création : « scan en cours » jusqu'à la fiche

  const state = {
    hasCard: () => Boolean(listing?.card_id || identification?.best_match),
    currentLanguage: () => listing?.language ?? identification?.language ?? null,
  };

  function render() {
    container.innerHTML = "";

    // En-tête : miniature du crop physique + miniature de référence + nom.
    const cropImg = el("img", { class: "crop-thumb", attrs: { src: crop.url, alt: crop.filename } });
    const thumbs = el("div", { class: "cb-thumbs" }, [cropImg]);

    const card = listing || (identification?.best_match ?? null);
    const refUrl = listing?.image_url ?? identification?.best_match?.image_url;
    if (refUrl) thumbs.append(el("img", { class: "ref-thumb", attrs: { src: refUrl, alt: "" } }));
    else if (loading) thumbs.append(el("div", { class: "ref-thumb skeleton sk-thumb" }));

    const title = el("div", { class: "cb-title" });
    if (card) {
      const name = listing?.card_name ?? identification?.best_match?.name ?? "Carte inconnue";
      const set = listing?.set_name ?? identification?.best_match?.set_name ?? "";
      const number = listing?.number ?? identification?.best_match?.number ?? "?";
      const rarity = listing?.rarity ?? identification?.best_match?.rarity ?? "";
      title.append(
        el("div", { class: "name", text: name }),
        el("div", { class: "set", text: `${set} — #${number}${rarity ? " · " + rarity : ""}` }),
      );
    } else if (loading) {
      title.append(el("div", { class: "skeleton sk-line w70" }), el("div", { class: "skeleton sk-line w45" }));
    } else {
      title.append(el("div", { class: "name muted", text: "Non identifiée" }));
    }

    const badges = el("div", { class: "cb-badges" });
    if (loading && !listing) {
      badges.append(el("span", { class: "loading-badge" }, [
        el("div", { class: "spinner" }),
        el("span", { text: identification ? "Génération de la fiche…" : "Identification…" }),
      ]));
    } else {
      if (identification) {
        badges.append(el("span", {
          class: `badge ${identification.confident ? "badge-ok" : "badge-warn"}`,
          text: identification.confident ? "Fiable" : "Incertain",
        }));
      }
      const lang = state.currentLanguage();
      badges.append(el("span", {
        class: "badge badge-lang",
        text: lang ? `${LANGUAGE_FLAGS[lang] || ""} ${lang}` : "Langue indéterminée",
      }));
    }
    title.append(badges);

    const header = el("div", { class: "cb-head" }, [thumbs, title]);
    container.append(header);

    if (crop.degraded) {
      container.append(el("div", { class: "cb-warn", text: "⚠ Détection en mode dégradé (fond texturé) — vérifie ce cadrage." }));
    }

    // Corps éditable : seulement quand la fiche est générée.
    if (listing) container.append(renderListingBody());
  }

  function renderListingBody() {
    const body = el("div");

    // Champs : langue, état, prix.
    const langSelect = selectField("Langue", LANGUAGE_OPTIONS.map((o) => ({ value: o.value, label: o.label })),
      listing.language ?? "", async (v) => { await save({ language: v }); render(); });

    const condSelect = selectField("État", conditions.map((c) => ({ value: c, label: c })),
      listing.condition ?? "", (v) => save({ condition: v }));

    const priceInput = el("input", { attrs: { type: "number", step: "0.5", min: "0", placeholder: "€" } });
    priceInput.value = listing.price ?? "";
    priceInput.addEventListener("change", () => {
      const price = priceInput.value === "" ? null : parseFloat(priceInput.value);
      save({ price });
      listing.price = price;
    });
    const estimateBtn = el("button", { class: "chip-btn", text: "Estimer", attrs: { title: "Cote Cardmarket (TCGdex) dans la langue détectée" } });
    const priceNote = el("div", { class: "price-note" });
    estimateBtn.addEventListener("click", async () => {
      estimateBtn.disabled = true; priceNote.textContent = "…"; priceNote.classList.remove("warn");
      try {
        const est = await api.fetchPriceEstimate(photoId, crop.filename);
        const unit = est.currency === "EUR" ? "€" : " " + est.currency;
        const parts = [`~${est.suggested}${unit}`];
        if (est.trend != null) parts.push(`tendance ${est.trend}€`);
        if (est.avg30 != null) parts.push(`moy 30j ${est.avg30}€`);
        parts.push(`(cote ${est.source_language})`);
        priceNote.textContent = parts.join(" · ");
        if (est.note) priceNote.classList.add("warn");
        if (est.suggested != null) { priceInput.value = est.suggested; await save({ price: est.suggested }); listing.price = est.suggested; }
      } catch (err) {
        priceNote.textContent = err.message; priceNote.classList.add("warn");
      } finally { estimateBtn.disabled = false; }
    });

    const priceField = el("div", { class: "f" }, [
      el("label", { class: "field-label", text: "Prix" }),
      el("div", { class: "price-row" }, [priceInput, estimateBtn]),
      priceNote,
    ]);

    body.append(el("div", { class: "cb-fields" }, [langSelect, condSelect, priceField]));

    // Textes (repliés par défaut pour la compacité sur demi-écran).
    const titleArea = textField("Titre", listing.title, 2, (v) => save({ title: v }));
    const descArea = textField("Description", listing.description, 5, (v) => save({ description: v }));
    const texts = el("details", { class: "cb-texts" }, [
      el("summary", { text: "Titre & description" }),
      titleArea.field, descArea.field,
    ]);
    body.append(texts);

    // Actions.
    const vintedBtn = el("button", { class: "btn btn-primary btn-sm", text: "Envoyer vers Vinted" });
    vintedBtn.addEventListener("click", async () => {
      vintedBtn.disabled = true;
      try {
        await api.stageForVinted({
          title: titleArea.value(),
          description: descArea.value(),
          price: priceInput.value === "" ? null : parseFloat(priceInput.value),
          condition: condSelect.querySelector("select").value,
        });
        const orig = vintedBtn.textContent;
        vintedBtn.textContent = "Prête ! Ouvre Vinted → Vendre";
        setTimeout(() => { vintedBtn.textContent = orig; }, 3500);
      } catch (err) { alert(err.message); } finally { vintedBtn.disabled = false; }
    });

    const regenBtn = el("button", { class: "chip-btn", text: "Régénérer le texte" });
    regenBtn.addEventListener("click", async () => {
      regenBtn.disabled = true;
      try { setListing(await api.regenerateListing(photoId, crop.filename)); }
      catch (err) { alert(err.message); } finally { regenBtn.disabled = false; }
    });

    body.append(el("div", { class: "cb-actions" }, [vintedBtn, regenBtn]));

    // Correction manuelle.
    body.append(renderCorrection());
    return body;
  }

  function renderCorrection() {
    const input = el("input", { attrs: { type: "search", placeholder: "Nom de la carte…" } });
    const results = el("div", { class: "search-results" });
    let timer;
    input.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const q = input.value.trim();
        if (q.length < 2) { results.innerHTML = ""; return; }
        try {
          const found = await api.searchReference(q);
          results.innerHTML = "";
          for (const r of found) results.append(candidateRow(r, r.card_id));
        } catch { /* ignore */ }
      }, 300);
    });

    const details = el("details", { class: "correct" }, [
      el("summary", { text: "Ce n'est pas la bonne carte ?" }),
      input, results,
    ]);

    // Alternatives issues de l'identification (si plusieurs candidats).
    if (identification?.candidates?.length > 1) {
      const altList = el("div", { class: "search-results" });
      for (const c of identification.candidates.slice(1)) altList.append(candidateRow(c, c.card_id, c.orb_score));
      details.append(el("details", { class: "alts" }, [el("summary", { text: "Autres possibilités détectées" }), altList]));
    }
    return details;
  }

  function candidateRow(candidate, cardId, score) {
    const chooseBtn = el("button", { class: "chip-btn", text: "Choisir" });
    chooseBtn.addEventListener("click", async () => {
      chooseBtn.disabled = true;
      try {
        await api.patchListing(photoId, crop.filename, { card_id: cardId });
        setListing(await api.regenerateListing(photoId, crop.filename));
      } catch (err) { alert(err.message); } finally { chooseBtn.disabled = false; }
    });
    return el("div", { class: "cand-row" }, [
      el("img", { attrs: { src: candidate.image_url, alt: "" } }),
      el("span", { class: "cl", text: `${candidate.name} · ${candidate.set_name} #${candidate.number}` }),
      score != null ? el("span", { class: "cs", text: `score ${score}` }) : null,
      chooseBtn,
    ]);
  }

  async function save(patch) {
    Object.assign(listing, patch);
    try { await api.patchListing(photoId, crop.filename, patch); }
    catch (err) { console.error(err); }
    updateSessionSummary();
  }

  function setIdentification(ident) { identification = ident; render(); }
  function setListing(l) { listing = l; loading = false; render(); }
  function setLoading(v) { loading = v; render(); }

  render();
  return {
    el: container,
    setIdentification,
    setListing,
    setLoading,
    hasListing: () => Boolean(listing),
    hasCard: state.hasCard,
    currentLanguage: state.currentLanguage,
  };
}

/* ── petits composants de champ ───────────────────────────────────────── */
function selectField(label, options, current, onChange) {
  const select = el("select");
  for (const opt of options) {
    const o = el("option", { text: opt.label, attrs: { value: opt.value } });
    if (String(opt.value) === String(current)) o.selected = true;
    select.append(o);
  }
  select.addEventListener("change", () => onChange(select.value));
  return el("div", { class: "f" }, [el("label", { class: "field-label", text: label }), select]);
}

function textField(label, value, rows, onChange) {
  const area = el("textarea", { attrs: { rows } });
  area.value = value ?? "";
  area.addEventListener("change", () => onChange(area.value));
  const copyBtn = el("button", { class: "chip-btn", text: "Copier" });
  copyBtn.addEventListener("click", () => copyToClipboard(area.value, copyBtn));
  const field = el("div", { class: "text-field" }, [
    el("div", { class: "tf-head" }, [el("label", { text: label }), copyBtn]),
    area,
  ]);
  return { field, value: () => area.value };
}
