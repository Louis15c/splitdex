/* Registre des sessions de scan (localStorage).
 *
 * Une « session » groupe les photos d'un même envoi — ce groupement n'existe
 * pas côté backend (qui indexe tout par photo_id), on le tient donc côté
 * client. Les données lourdes (crops, identifications, fiches) restent
 * côté serveur et sont re-téléchargées à l'ouverture d'une session ; ici on
 * ne stocke que l'ossature : quelles photos, quand, et un résumé pour
 * l'historique. Suffisant pour un outil local mono-utilisateur. */

const SESSIONS_KEY = "splitdex.sessions.v1";

export function loadSessions() {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveSessions(list) {
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(list));
}

export function createSession(photos) {
  const id = "s" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  const session = {
    id,
    createdAt: Date.now(),
    photoIds: photos.map((p) => p.id),
    photoUrls: Object.fromEntries(photos.map((p) => [p.id, p.url])),
    coverUrl: photos[0]?.url ?? null,
    photoCount: photos.length,
    cardCount: null, // rempli après identification
    languages: null, // { Français: 12, Anglaise: 3, ... }
  };
  const all = loadSessions();
  all.unshift(session);
  saveSessions(all);
  return session;
}

export function getSession(id) {
  return loadSessions().find((s) => s.id === id) ?? null;
}

export function updateSession(id, patch) {
  const all = loadSessions();
  const idx = all.findIndex((s) => s.id === id);
  if (idx < 0) return;
  all[idx] = { ...all[idx], ...patch };
  saveSessions(all);
}

export function deleteSession(id) {
  saveSessions(loadSessions().filter((s) => s.id !== id));
}
