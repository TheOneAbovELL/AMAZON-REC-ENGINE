import { getLexicalEngine, UnknownProductError } from "../../lib/engine/index.mjs";
import { backendUrl, BackendUnavailableError, callBackend } from "../../lib/server/backend.mjs";
import { validateSimilarRequest, ValidationError } from "../../lib/server/validate.mjs";

export default async function handler(req, res) {
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ error: "Method not allowed. Use GET." });
  }
  let request;
  try {
    request = validateSimilarRequest(req.query);
  } catch (err) {
    if (err instanceof ValidationError) return res.status(400).json({ error: err.message });
    throw err;
  }

  let notice = "Similar items by keyword overlap: no semantic backend is configured for this deployment.";
  let degraded = false;
  if (backendUrl()) {
    try {
      const { status, data } = await callBackend(`/api/products/${request.asin}/similar?k=${request.k}`);
      if (status === 200) {
        res.setHeader("Cache-Control", "public, max-age=300");
        return res.status(200).json({ ...data, served_by: "python-backend" });
      }
      if (status === 404 || status === 400) return res.status(status).json(data);
      notice = `The semantic backend returned an error (${status}); similar items use keyword overlap.`;
    } catch (err) {
      if (!(err instanceof BackendUnavailableError)) throw err;
      console.warn("similar: falling back to keyword engine:", err.message);
      notice = "The semantic backend is unreachable; similar items use keyword overlap.";
    }
    degraded = true;
  }

  try {
    const result = getLexicalEngine().similar(request.asin, request.k);
    result.engine = { ...result.engine, degraded, notice };
    res.setHeader("Cache-Control", degraded ? "no-store" : "public, max-age=300");
    return res.status(200).json({ ...result, served_by: "next-lexical" });
  } catch (err) {
    if (err instanceof UnknownProductError) return res.status(404).json({ error: `Unknown product ${request.asin}.` });
    console.error("similar: keyword engine failed", err);
    return res.status(500).json({ error: "Could not compute similar products." });
  }
}
