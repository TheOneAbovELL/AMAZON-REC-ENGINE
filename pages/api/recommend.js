import { getCatalogMeta, getConfig, getLexicalEngine, InvalidRequestError } from "../../lib/engine/index.mjs";
import { backendUrl, BackendUnavailableError, callBackend } from "../../lib/server/backend.mjs";
import { validateRecommendRequest, ValidationError } from "../../lib/server/validate.mjs";

export const config = { api: { bodyParser: { sizeLimit: "8kb" } } };

const NOT_CONFIGURED = "Keyword ranking: no semantic backend is configured for this deployment.";

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Method not allowed. Use POST." });
  }

  let request;
  try {
    const engineConfig = getConfig();
    request = validateRecommendRequest(req.body, {
      profiles: Object.keys(engineConfig.profiles),
      departments: getCatalogMeta().departments.map((d) => d.name),
    });
  } catch (err) {
    if (err instanceof ValidationError) return res.status(400).json({ error: err.message });
    console.error("recommend: failed to load engine configuration", err);
    return res.status(500).json({ error: "The recommendation service is misconfigured." });
  }

  let notice = NOT_CONFIGURED;
  let degraded = false;
  if (backendUrl()) {
    try {
      const { status, data } = await callBackend("/api/recommend", { method: "POST", body: request });
      if (status === 200) return res.status(200).json({ ...data, served_by: "python-backend" });
      if (status >= 400 && status < 500 && status !== 429) return res.status(status).json(data);
      notice =
        status === 503
          ? "The semantic backend is still starting up; showing keyword results meanwhile."
          : `The semantic backend returned an error (${status}); showing keyword results.`;
    } catch (err) {
      if (!(err instanceof BackendUnavailableError)) throw err;
      console.warn("recommend: falling back to keyword engine:", err.message);
      notice = "The semantic backend is unreachable; showing keyword results.";
    }
    degraded = true;
  }

  try {
    const result = getLexicalEngine().recommend(request.query, {
      profile: request.profile,
      topK: request.top_k,
      filters: request.filters,
    });
    result.engine = { ...result.engine, degraded, notice };
    return res.status(200).json({ ...result, served_by: "next-lexical" });
  } catch (err) {
    if (err instanceof InvalidRequestError) return res.status(400).json({ error: err.message });
    console.error("recommend: keyword engine failed", err);
    return res.status(500).json({ error: "Could not compute recommendations." });
  }
}
