# Aisle: explainable product recommendations

A product recommendation engine over a **33,670-product Amazon India catalog snapshot (March 2023)**.
Shoppers describe what they want in plain language, budgets included ("laptop for AI under 90k").
Results blend semantic similarity, keyword matching, rating quality, popularity, discount and a
shopper profile, and **every result shows the signals that ranked it**.

- **Hybrid retrieval**: MiniLM sentence embeddings (FAISS) + BM25 keyword search + product-type matching
- **Query understanding**: budgets ("under ₹2,000", "between 60k and 1 lakh", "around 15000"), product
  type with accessory handling ("laptop" ≠ "laptop bag"), spelling and unit normalisation ("43 inches" = "43 inch")
- **Multi-signal ranking**: relevance, Bayesian-smoothed rating, popularity, discount, profile fit
- **Shopper profiles**: General, Student (portable and cheaper), AI/ML builder (GPU, RAM), Gamer
- **Similar items**: item-to-item nearest neighbours for any product
- **Graceful degradation**: without the Python backend, the web app serves an identical keyword-only
  pipeline and says so in the UI

> Independent portfolio project, not affiliated with Amazon. Prices and ratings are from the 2023 snapshot.

## Architecture

```
 Browser ──► Next.js (pages/, Vercel or Docker)
               │  /api/recommend  /api/similar  /api/catalog  /api/health
               │
               ├── BACKEND_URL set and healthy ──► Python API (api_server.py, FastAPI)
               │                                     hybrid engine: MiniLM + FAISS + BM25 + ranking
               │
               └── otherwise ──► lib/engine (JavaScript keyword engine, same pipeline minus embeddings)

 Shared by both engines:  config/engine.json         weights, query rules, product types, profiles
                          data/processed/catalog.json the product catalog (built by scripts/build_catalog.py)
```

The JavaScript fallback mirrors the Python engine's keyword mode exactly; `tests/test_parity.py`
runs both on the same requests and requires identical rankings, scores and explanations.
See [docs/system_design.md](docs/system_design.md) for the pipeline, scoring formula and trade-offs.

## Quality

`python -m scripts.evaluate` on 32 rule-labelled queries (k = 10, full catalog):

| System | Precision@10 | nDCG@10 | MRR | Results over budget | p95 latency |
|---|---|---|---|---|---|
| dense-only (embeddings, no ranking) | 0.875 | 0.953 | 0.954 | 8 | 71 ms |
| lexical (the web fallback) | 0.881 | 0.941 | 0.896 | 0 | 93 ms |
| **hybrid** (the Python API) | **0.969** | **0.996** | **1.000** | **0** | 107 ms |

Labels are regex rules on product name and price (`eval/queries.json`), written independently of the
engine's own product-type patterns. They check that results are the right kind of product within budget.
They are not human relevance judgements. Latency measured on a 6-core laptop CPU.
Full per-query results: [results/evaluation_report.md](results/evaluation_report.md).

## Quick start

Requirements: Python 3.11+ (tested on 3.13), Node.js 20+ (tested on 22).

```bash
# 1. Python API (semantic engine)
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements-dev.txt
python -m scripts.build_index     # encodes the catalog once: ~5–8 min on CPU, downloads ~90 MB model
uvicorn api_server:app --port 8000

# 2. Web app (another terminal)
npm install
echo BACKEND_URL=http://127.0.0.1:8000 > .env.local
npm run build && npm start        # http://localhost:3000   (or: npm run dev)
```

Without step 1 (or without `BACKEND_URL`), the web app still works using the keyword engine.

Other entry points:

```bash
python run_pipeline.py "wireless earbuds under 2000" --profile student   # CLI
pip install -r requirements-dashboard.txt && streamlit run app.py         # analyst console
docker compose up --build                                                 # full stack on :3000
```

## Tests and checks

```bash
pytest                 # 65 tests: parser, ranking, engine, API contract, JS/Python parity, real model
pytest -m "not model"  # skip the tests that load the real embedding model
npm test               # 17 tests: JS engine + Next.js API routes (incl. backend fallback)
npm run lint
ruff check . && ruff format --check src tests api_server.py
python -m scripts.evaluate
```

## Configuration

| Variable | Used by | Default | Purpose |
|---|---|---|---|
| `BACKEND_URL` | web | unset | Python API base URL. Unset or unreachable means the keyword engine answers. |
| `BACKEND_TIMEOUT_MS` | web | `8000` | Time to wait for the API before falling back |
| `PORT` | api | `8000` | Listen port (Docker) |
| `ALLOWED_ORIGINS` | api | empty | Comma-separated browser origins for CORS. Not needed for server-to-server calls. |
| `RATE_LIMIT_PER_MINUTE` | api | `120` | Per-IP limit, in-process (`0` disables) |
| `AUTO_BUILD_INDEX` | api | `true` | Rebuild embeddings at startup if missing or stale |
| `ALLOW_LEXICAL_FALLBACK` | api | `true` | Serve keyword results if the model can't load, instead of failing |
| `EMBEDDING_MODEL` | api | `sentence-transformers/all-MiniLM-L6-v2` | Changing it forces an embedding rebuild |
| `QUERY_LOG_PATH` | api | unset | Optional JSON-lines query log. Off by default because queries can contain personal data. |
| `LOG_LEVEL` | api | `INFO` | |

See [.env.example](.env.example). No secrets are required.

## Deployment

**Web on Vercel.** Import the repository (framework: Next.js). The catalog and config ship with the
functions (`outputFileTracingIncludes` in `next.config.mjs`). Set `BACKEND_URL` to enable semantic search.

**Python API** on any container host with **≥ 1 GB RAM** (Render, Railway, Fly.io, Cloud Run, a VM):
`docker build -t rec-engine-api .` The image bakes in the model and the embeddings, so it starts
offline in about 30–40 s. Health: `GET /api/health` (liveness), `GET /api/ready` (readiness, 503 while loading).
Run one replica per ~1 GB. The rate limiter is per-process, so put a gateway limiter in front for multi-replica setups.

**Rollback.** Both services are stateless. Redeploy the previous image or commit. A catalog change ships
as a new `catalog.json`, and the API rebuilds embeddings when the catalog hash changes.

## Data pipeline

```bash
python -m scripts.build_catalog   # data/raw/Amazon-Products.csv  ->  data/processed/catalog.json + catalog_meta.json
python -m scripts.build_index     # catalog.json  ->  models/embeddings.npy + models/manifest.json
```

`build_catalog` keeps listings with a price and at least 20 ratings, collapses colour and size variants,
balances departments, and guarantees coverage of every product type the parser understands. The raw
export (`data/raw/`, ~1.8 GB) is not committed. `models/manifest.json` records the catalog hash, so stale
embeddings are detected and never silently served.

## Project layout

```
api_server.py            FastAPI app (validation, readiness, rate limit, request IDs)
src/                     Python engine: query_parser, lexical (BM25), embeddings, vector_store (FAISS),
                         ranking, personalization, explainer, recommender (orchestrator), catalog
lib/engine/              JavaScript keyword engine (mirror of the Python lexical mode)
lib/server/              Next.js request validation and backend client
pages/, components/, styles/   Next.js UI and API routes
config/engine.json       shared ranking weights, query rules, product types, profiles
scripts/                 build_catalog, build_index, evaluate, js_engine_cli (parity tests)
tests/                   pytest suites, tests/js (node:test), shared fixtures
eval/queries.json        evaluation queries and relevance rules
app.py, run_pipeline.py  Streamlit analyst console, CLI
```

## Known limitations

- The catalog is a **2023 snapshot**: prices, ratings and availability are not live, and there is no stock data.
- The source export has **few laptops** (~85 listings match the laptop type), so laptop results are thin compared to audio, TVs or fashion.
- Personalisation uses **declared profiles**, not behaviour. There is no user history, click feedback or collaborative filtering yet.
- Relevance labels are rule-based (silver standard). There are no human-judged or online (A/B) metrics.
- Product images are hot-linked from Amazon's public CDN and may disappear.

## Author

Omjee R Giri
