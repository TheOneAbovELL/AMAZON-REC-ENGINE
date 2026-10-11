// Runs the JavaScript keyword engine on a batch of requests; used by tests/test_parity.py.
// Usage: node scripts/js_engine_cli.mjs <requests.json>
//   requests.json = { "catalog": "<path>", "config": "<path>", "requests": [
//     { "type": "recommend", "query": "...", "profile": "general", "top_k": 5, "filters": {} },
//     { "type": "similar", "asin": "...", "k": 5 } ] }

import fs from "node:fs";

import { LexicalEngine } from "../lib/engine/engine.mjs";

const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf-8"));
const engine = new LexicalEngine(
  JSON.parse(fs.readFileSync(spec.catalog, "utf-8")),
  JSON.parse(fs.readFileSync(spec.config, "utf-8")),
);
const results = spec.requests.map((r) =>
  r.type === "similar"
    ? engine.similar(r.asin, r.k)
    : engine.recommend(r.query, { profile: r.profile, topK: r.top_k, filters: r.filters || {} }),
);
process.stdout.write(JSON.stringify(results));
