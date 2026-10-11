import { getCatalogMeta, getConfig } from "../../lib/engine/index.mjs";

// Catalog statistics, departments and shopper profiles. Served from the build artefacts
// shared with the Python backend, so it works with or without BACKEND_URL.
export default function handler(req, res) {
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ error: "Method not allowed. Use GET." });
  }
  try {
    const meta = getCatalogMeta();
    const profiles = Object.fromEntries(
      Object.entries(getConfig().profiles).map(([id, p]) => [id, { label: p.label, description: p.description }]),
    );
    res.setHeader("Cache-Control", "public, max-age=60, stale-while-revalidate=300");
    return res.status(200).json({ ...meta, profiles });
  } catch (err) {
    console.error("catalog: failed to read catalog metadata", err);
    return res.status(500).json({ error: "Catalog metadata is unavailable." });
  }
}
