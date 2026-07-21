import { uploadPhotos, getDbStatus } from "./api.js";
import { createSession, loadSessions } from "./session-store.js";
import { MAX_PHOTOS_PER_BATCH, el, formatDate, mountNav } from "./common.js";

mountNav("home");

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const browseBtn = document.getElementById("browse-btn");
const statusEl = document.getElementById("status");

/* ── Upload → création de session → redirection vers sa page dédiée ────── */
async function handleFiles(fileList) {
  const files = Array.from(fileList).filter((f) => f.type.startsWith("image/"));
  if (!files.length) return;
  if (files.length > MAX_PHOTOS_PER_BATCH) {
    statusEl.textContent = `Trop de photos (${files.length}) : maximum ${MAX_PHOTOS_PER_BATCH} par session.`;
    return;
  }

  statusEl.textContent = `Envoi de ${files.length} photo${files.length > 1 ? "s" : ""}…`;
  browseBtn.style.pointerEvents = "none";
  try {
    const { photos } = await uploadPhotos(files);
    const session = createSession(photos);
    statusEl.textContent = "Session créée, ouverture…";
    // La découpe + l'identification se font sur la page de scan dédiée.
    window.location.href = `/scan?s=${session.id}`;
  } catch (err) {
    statusEl.textContent = `Erreur : ${err.message}`;
    browseBtn.style.pointerEvents = "";
  }
}

browseBtn.addEventListener("click", (e) => { e.stopPropagation(); fileInput.click(); });
dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => handleFiles(fileInput.files));

// Glisser-déposer
["dragenter", "dragover"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("drag"); })
);
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("drag"); })
);
dropzone.addEventListener("drop", (e) => {
  if (e.dataTransfer?.files?.length) handleFiles(e.dataTransfer.files);
});

// Coller depuis le presse-papier (capture d'écran, image copiée)
window.addEventListener("paste", (e) => {
  const files = Array.from(e.clipboardData?.files ?? []).filter((f) => f.type.startsWith("image/"));
  if (files.length) handleFiles(files);
});

/* ── Statistique base de référence ────────────────────────────────────── */
getDbStatus()
  .then(({ cached_cards }) => {
    document.getElementById("stat-cards").textContent = cached_cards.toLocaleString("fr-FR");
  })
  .catch(() => { document.getElementById("stat-cards").textContent = "—"; });

/* ── Sessions récentes ────────────────────────────────────────────────── */
function renderRecentSessions() {
  const container = document.getElementById("recent-sessions");
  const sessions = loadSessions().slice(0, 3);
  container.innerHTML = "";
  if (!sessions.length) {
    container.append(el("div", { class: "clay empty-sessions", text: "Aucune session pour l'instant — déposez vos premières photos ci-dessus." }));
    return;
  }
  for (const s of sessions) container.append(renderSessionRow(s));
}

function renderSessionRow(s) {
  const summary = s.cardCount != null
    ? `${s.cardCount} carte${s.cardCount > 1 ? "s" : ""}${languageSummary(s.languages)}`
    : `${s.photoCount} photo${s.photoCount > 1 ? "s" : ""} · en attente de traitement`;
  return el("a", { class: "clay press session-row", attrs: { href: `/scan?s=${s.id}` } }, [
    s.coverUrl ? el("img", { class: "cover", attrs: { src: s.coverUrl, alt: "" } }) : el("div", { class: "cover" }),
    el("div", { class: "meta" }, [
      el("div", { class: "t", text: formatDate(s.createdAt) }),
      el("div", { class: "d", text: summary }),
    ]),
  ]);
}

function languageSummary(languages) {
  if (!languages) return "";
  const parts = Object.entries(languages).filter(([, n]) => n > 0);
  if (!parts.length) return "";
  return " · " + parts.map(([lang, n]) => `${lang.slice(0, 2).toUpperCase()} ${n}`).join(" ");
}

renderRecentSessions();
