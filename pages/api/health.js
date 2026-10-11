import { getCatalogMeta } from "../../lib/engine/index.mjs";
import { backendUrl, BackendUnavailableError, callBackend } from "../../lib/server/backend.mjs";

// Reports which engine will answer /api/recommend right now. Never exposes the backend URL.
export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  let catalog = null;
  try {
    const meta = getCatalogMeta();
    catalog = { products: meta.total_products, snapshot: meta.snapshot };
  } catch (err) {
    console.error("health: catalog metadata unavailable", err);
    return res.status(503).json({ status: "error", error: "Catalog metadata is unavailable." });
  }

  const backend = { configured: Boolean(backendUrl()), ready: false, mode: null, model: null };
  if (backend.configured) {
    try {
      const { status, data } = await callBackend("/api/ready", { timeoutMs: 2500 });
      backend.ready = status === 200;
      backend.mode = data?.engine?.mode ?? null;
      backend.model = data?.engine?.model ?? null;
      if (!backend.ready) backend.state = data?.status ?? `http ${status}`;
    } catch (err) {
      if (!(err instanceof BackendUnavailableError)) throw err;
      backend.state = "unreachable";
    }
  }
  const mode = backend.ready ? backend.mode || "hybrid" : "lexical";
  return res.status(200).json({ status: "ok", mode, backend, catalog, timestamp: new Date().toISOString() });
}
