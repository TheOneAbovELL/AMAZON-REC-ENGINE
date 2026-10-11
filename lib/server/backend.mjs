// Client for the optional Python semantic backend (api_server.py), configured by BACKEND_URL.

export class BackendUnavailableError extends Error {}

export function backendUrl() {
  const raw = (process.env.BACKEND_URL || "").trim();
  if (!raw) return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    return url.toString().replace(/\/+$/, "");
  } catch {
    return null;
  }
}

export const BACKEND_TIMEOUT_MS = Number(process.env.BACKEND_TIMEOUT_MS) || 8000;

// Returns { status, data } for any HTTP response; throws BackendUnavailableError on network
// failure, timeout or a non-JSON reply.
export async function callBackend(path, { method = "GET", body, timeoutMs = BACKEND_TIMEOUT_MS } = {}) {
  const base = backendUrl();
  if (!base) throw new BackendUnavailableError("BACKEND_URL is not configured.");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${base}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json", Accept: "application/json" } : { Accept: "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new BackendUnavailableError(`Backend returned a non-JSON ${response.status} response.`);
    }
    return { status: response.status, data };
  } catch (err) {
    if (err instanceof BackendUnavailableError) throw err;
    const reason = err?.name === "AbortError" ? `timed out after ${timeoutMs} ms` : err?.message || "network error";
    throw new BackendUnavailableError(`Backend unreachable: ${reason}.`);
  } finally {
    clearTimeout(timer);
  }
}
