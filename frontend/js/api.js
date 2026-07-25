/* Enveloppe des endpoints backend (voir README / backend/app/api). */

async function jsonOrThrow(response, fallbackMessage) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || fallbackMessage);
  return data;
}

export async function uploadPhotos(files) {
  const formData = new FormData();
  for (const file of files) formData.append("files", file);
  const response = await fetch("/api/upload", { method: "POST", body: formData });
  return jsonOrThrow(response, "Échec de l'upload"); // { photos: [...] }
}

export async function getCrops(photoId) {
  const response = await fetch(`/api/photos/${photoId}/crops`);
  return jsonOrThrow(response, "Crops indisponibles");
}

export async function runCrops(photoId) {
  const response = await fetch(`/api/photos/${photoId}/crops`, { method: "POST" });
  return jsonOrThrow(response, "Échec de la détection");
}

export async function getIdentifications(photoId) {
  const response = await fetch(`/api/photos/${photoId}/identify`);
  return jsonOrThrow(response, "Identifications indisponibles");
}

export async function runIdentify(photoId, signal) {
  const response = await fetch(`/api/photos/${photoId}/identify`, { method: "POST", signal });
  return jsonOrThrow(response, "Échec de l'identification");
}

export async function getListings(photoId) {
  const response = await fetch(`/api/photos/${photoId}/listings`);
  return jsonOrThrow(response, "Fiches indisponibles");
}

export async function generateListings(photoId, signal) {
  const response = await fetch(`/api/photos/${photoId}/listings/generate`, { method: "POST", signal });
  return jsonOrThrow(response, "Échec de la génération");
}

export async function patchListing(photoId, cropFilename, patch) {
  const response = await fetch(`/api/photos/${photoId}/listings/${cropFilename}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return jsonOrThrow(response, "Échec de la mise à jour");
}

export async function regenerateListing(photoId, cropFilename) {
  const response = await fetch(`/api/photos/${photoId}/listings/${cropFilename}/regenerate`, { method: "POST" });
  return jsonOrThrow(response, "Échec de la régénération");
}

export async function fetchPriceEstimate(photoId, cropFilename) {
  const response = await fetch(`/api/photos/${photoId}/listings/${cropFilename}/price-estimate`);
  return jsonOrThrow(response, "Estimation indisponible");
}

export async function stageForVinted(listing) {
  const response = await fetch("/api/vinted/staged", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(listing),
  });
  return jsonOrThrow(response, "Échec de l'envoi vers Vinted");
}

export async function searchReference(query) {
  const response = await fetch(`/api/reference/search?q=${encodeURIComponent(query)}`);
  return jsonOrThrow(response, "Recherche indisponible");
}

let conditionsCache = null;
export async function getConditions() {
  if (!conditionsCache) {
    const response = await fetch("/api/reference/conditions");
    conditionsCache = await jsonOrThrow(response, "Conditions indisponibles");
  }
  return conditionsCache;
}

export async function getDbStatus() {
  const response = await fetch("/api/reference/status");
  return jsonOrThrow(response, "Base injoignable"); // { cached_cards }
}

export function exportUrl(photoId) {
  return `/api/photos/${photoId}/export`;
}
