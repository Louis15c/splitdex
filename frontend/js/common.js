/* Constantes et petits helpers partagés par les pages. */

export const MAX_PHOTOS_PER_BATCH = 20; // aligné sur config.py côté serveur

export const LANGUAGE_FLAGS = {
  Français: "🇫🇷",
  Anglaise: "🇬🇧",
  Japonaise: "🇯🇵",
  Allemande: "🇩🇪",
  Espagnole: "🇪🇸",
  Italienne: "🇮🇹",
};

export const LANGUAGE_OPTIONS = [
  { value: "", label: "Langue non déterminée" },
  { value: "Français", label: `${LANGUAGE_FLAGS.Français} Français` },
  { value: "Anglaise", label: `${LANGUAGE_FLAGS.Anglaise} Anglaise` },
  { value: "Japonaise", label: `${LANGUAGE_FLAGS.Japonaise} Japonaise` },
  { value: "Allemande", label: `${LANGUAGE_FLAGS.Allemande} Allemande` },
  { value: "Espagnole", label: `${LANGUAGE_FLAGS.Espagnole} Espagnole` },
  { value: "Italienne", label: `${LANGUAGE_FLAGS.Italienne} Italienne` },
];

export function el(tag, opts = {}, children = []) {
  const node = document.createElement(tag);
  if (opts.class) node.className = opts.class;
  if (opts.text != null) node.textContent = opts.text;
  if (opts.html != null) node.innerHTML = opts.html;
  if (opts.attrs) for (const [k, v] of Object.entries(opts.attrs)) node.setAttribute(k, v);
  if (opts.on) for (const [ev, fn] of Object.entries(opts.on)) node.addEventListener(ev, fn);
  for (const child of children) if (child) node.append(child);
  return node;
}

export function formatDate(ts) {
  const d = new Date(ts);
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "long" }) +
    " · " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

export function copyToClipboard(text, button) {
  navigator.clipboard.writeText(text).then(() => {
    const original = button.textContent;
    button.textContent = "Copié !";
    setTimeout(() => { button.textContent = original; }, 1500);
  });
}

/** Marque de la Pokéball SVG pour le logo (dessin ligne, pas d'emoji). */
export const BRAND_MARK_SVG =
  '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round">' +
  '<circle cx="12" cy="12" r="9"/><path d="M3 12h6M15 12h6"/><circle cx="12" cy="12" r="2.6"/></svg>';

/** En-tête de navigation commun, injecté en tête de chaque page. */
export function mountNav(active) {
  const bar = el("div", { class: "navbar" }, [
    el("div", { class: "clay nav" }, [
      el("a", { class: "brand", attrs: { href: "/" }, html: `<span class="mark">${BRAND_MARK_SVG}</span>Splitdex` }),
      el("div", { class: "spacer" }),
      el("div", { class: "nav-links" }, [
        el("a", { text: "Accueil", class: active === "home" ? "on" : "", attrs: { href: "/" } }),
        el("a", { text: "Historique", class: active === "history" ? "on" : "", attrs: { href: "/history" } }),
      ]),
    ]),
  ]);
  document.body.prepend(bar);
}
