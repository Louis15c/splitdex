import { loadSessions, deleteSession } from "./session-store.js";
import { el, formatDate, mountNav, LANGUAGE_FLAGS } from "./common.js";

mountNav("history");

const list = document.getElementById("history-list");

function render() {
  const sessions = loadSessions();
  list.innerHTML = "";

  if (!sessions.length) {
    list.append(
      el("div", { class: "clay empty" }, [
        el("h2", { text: "Aucune session pour l'instant" }),
        el("p", { text: "Vos sessions de scan apparaîtront ici." }),
        el("a", { class: "btn btn-primary", attrs: { href: "/", style: "margin-top:16px" }, text: "Scanner des cartes" }),
      ])
    );
    return;
  }

  for (const s of sessions) list.append(renderRow(s));
}

function renderRow(s) {
  const summary = s.cardCount != null
    ? `${s.cardCount} carte${s.cardCount > 1 ? "s" : ""} identifiée${s.cardCount > 1 ? "s" : ""} · ${s.photoCount} photo${s.photoCount > 1 ? "s" : ""}`
    : `${s.photoCount} photo${s.photoCount > 1 ? "s" : ""} · pas encore traitée`;

  const langs = el("div", { class: "langs" });
  if (s.languages) {
    for (const [lang, n] of Object.entries(s.languages)) {
      if (n > 0) langs.append(el("span", { class: "badge badge-lang", text: `${LANGUAGE_FLAGS[lang] || ""} ${n}` }));
    }
  }

  const delBtn = el("button", {
    class: "chip-btn del-btn",
    text: "Supprimer",
    on: {
      click: () => {
        if (confirm("Retirer cette session de l'historique ? (les photos restent sur le serveur)")) {
          deleteSession(s.id);
          render();
        }
      },
    },
  });

  return el("div", { class: "clay hist-row" }, [
    el("a", { attrs: { href: `/scan?s=${s.id}` } }, [
      s.coverUrl ? el("img", { class: "cover", attrs: { src: s.coverUrl, alt: "" } }) : el("div", { class: "cover" }),
    ]),
    el("a", { class: "meta", attrs: { href: `/scan?s=${s.id}` } }, [
      el("div", { class: "t", text: formatDate(s.createdAt) }),
      el("div", { class: "d", text: summary }),
      langs,
    ]),
    delBtn,
  ]);
}

render();
