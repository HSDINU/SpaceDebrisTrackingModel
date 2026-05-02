import type { VizPayload } from "./vizTypes";

/**
 * Route handler süreç belleğinde tutulan son başarılı payload.
 * Dosya imzası aynıysa disk/parse atlanır (UI ve API yanıt süresi kısalır).
 */
let entry: { signature: string; payload: VizPayload } | null = null;

export function getCachedVizPayload(signature: string): VizPayload | null {
  if (entry?.signature === signature) return entry.payload;
  return null;
}

export function setCachedVizPayload(signature: string, payload: VizPayload): void {
  entry = { signature, payload };
}

export function clearVizPayloadRouteCache(): void {
  entry = null;
}
