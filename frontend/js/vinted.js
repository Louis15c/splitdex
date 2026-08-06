import * as api from "./api.js";
import { el, formatDate, mountNav } from "./common.js";

mountNav("vinted");

/* ── Annonces reprises pour republication ──────────────────────────────
   Alimentées par le bouton « Reprendre dans Splitdex » du userscript, sur la
   page d'une annonce déjà publiée. Ici on relit la fiche, on récupère les
   photos recadrées, et on renvoie le texte vers le formulaire Vinted par la
   mécanique de remplissage existante. La publication reste manuelle. */

const list = document.getElementById("republish-list");

function card(entry) {
  const photos = el("div", { class: "rp-photos" });
  for (const filename of entry.photos.slice(0, 6)) {
    photos.append(el("img", { attrs: { src: `/api/republish/${entry.id}/photos/${filename}`, alt: "" } }));
  }

  const sendBtn = el("button", { class: "btn btn-primary btn-sm", text: "Envoyer vers Vinted" });
  sendBtn.addEventListener("click", async () => {
    sendBtn.disabled = true;
    try {
      await api.stageForVinted({
        title: entry.title,
        description: entry.description || "",
        price: entry.price,
        condition: entry.condition,
      });
      const original = sendBtn.textContent;
      sendBtn.textContent = "Prête ! Ouvre Vinted → Vendre";
      setTimeout(() => { sendBtn.textContent = original; }, 3500);
    } catch (err) {
      alert(err.message);
    } finally {
      sendBtn.disabled = false;
    }
  });

  const zipBtn = el("a", {
    class: "chip-btn",
    text: `⤓ Photos (${entry.photos.length})`,
    attrs: { href: api.republishPhotosUrl(entry.id), download: "" },
  });

  const delBtn = el("button", { class: "chip-btn", text: "Retirer" });
  delBtn.addEventListener("click", async () => {
    delBtn.disabled = true;
    try { await api.deleteRepublished(entry.id); await render(); }
    catch (err) { alert(err.message); delBtn.disabled = false; }
  });

  const missing = entry.photos_requested - entry.photos.length;
  return el("div", { class: "clay rp-card" }, [
    el("div", { class: "rp-head" }, [
      el("div", { class: "rp-meta" }, [
        el("div", { class: "t", text: entry.title }),
        el("div", { class: "d", text: [
          entry.price != null ? `${entry.price} €` : null,
          entry.condition,
          formatDate(entry.captured_at),
        ].filter(Boolean).join(" · ") }),
      ]),
    ]),
    entry.photos.length ? photos : el("div", { class: "d", text: "Aucune photo récupérée." }),
    missing > 0 ? el("div", { class: "rp-warn", text: `⚠ ${missing} photo(s) n'ont pas pu être téléchargées.` }) : null,
    el("div", { class: "rp-actions" }, [sendBtn, zipBtn, delBtn]),
  ]);
}

async function render() {
  list.innerHTML = "";
  let entries = [];
  try {
    entries = await api.getRepublished();
  } catch {
    list.append(el("div", { class: "rp-empty", text: "Impossible de lire les annonces reprises." }));
    return;
  }
  if (!entries.length) {
    list.append(el("div", { class: "rp-empty" }, [
      el("p", { text: "Aucune annonce reprise pour l'instant." }),
      el("p", { class: "sub", text: "Ouvre une de tes annonces sur Vinted et clique sur « ♻️ Reprendre dans Splitdex »." }),
    ]));
    return;
  }
  for (const entry of entries) list.append(card(entry));
}

render();
