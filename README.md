 <div align="center">

# 🛍️ Aisle
### Explainable Product Recommendations

**Find the right product using natural-language search, hybrid retrieval, multi-signal ranking, and personalized recommendations.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-Web%20App-000000?logo=next.js&logoColor=white)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python%20API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![FAISS](https://img.shields.io/badge/FAISS-Vector%20Search-00599C)](https://github.com/facebookresearch/faiss)
[![Node.js](https://img.shields.io/badge/Node.js-20%2B-339933?logo=nodedotjs&logoColor=white)](https://nodejs.org/)

[Quick Start](#quick-start) · [Architecture](#architecture) · [Quality](#quality) · [API](#api-endpoints) · [Deployment](#deployment) · [Limitations](#known-limitations)

</div>

---

A product recommendation engine over a **33,670-product Amazon India catalog snapshot (March 2023)**.

Shoppers describe what they want in plain language, budgets included — for example, `"laptop for AI under 90k"`. Results blend semantic similarity, keyword matching, rating quality, popularity, discount and a shopper profile, and **every result shows the signals that ranked it**.

## ✨ Key Features

| Feature | Description |
|---|---|
| **Hybrid retrieval** | MiniLM sentence embeddings (FAISS) + BM25 keyword search + product-type matching |
| **Query understanding** | Budgets (`"under ₹2,000"`, `"between 60k and 1 lakh"`, `"around 15000"`), product type with accessory handling (`"laptop" ≠ "laptop bag"`), spelling and unit normalisation (`"43 inches" = "43 inch"`) |
| **Multi-signal ranking** | Relevance, Bayesian-smoothed rating, popularity, discount, profile fit |
| **Shopper profiles** | General, Student (portable and cheaper), AI/ML builder (GPU, RAM), Gamer |
| **Similar items** | Item-to-item nearest neighbours for any product |
| **Graceful degradation** | Without the Python backend, the web app serves an identical keyword-only pipeline and says so in the UI |

> **Project note:** Independent portfolio project, not affiliated with Amazon. Prices and ratings are from the 2023 snapshot.

---

## Contents

- [Architecture](#architecture)
- [Quality](#quality)
- [Quick start](#quick-start)
- [Other entry points](#other-entry-points)
- [Tests and checks](#tests-and-checks)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Data pipeline](#data-pipeline)
- [Project layout](#project-layout)
- [Known limitations](#known-limitations)
- [Author](#author)

---

## Architecture

```text
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

The JavaScript fallback mirrors the Python engine's keyword mode exactly; `tests/test_parity.py` runs both on the same requests and requires identical rankings, scores and explanations.

See [docs/system_design.md](docs/system_design.md) for the pipeline, scoring formula and trade-offs.

### Request flow

1. The shopper submits a natural-language product query through the Next.js application.
2. The web application checks the configured Python API backend.
3. When `BACKEND_URL` is set and the backend is healthy, the Python API uses the hybrid engine: MiniLM + FAISS + BM25 + ranking.
4. Otherwise, `lib/engine` serves keyword-based results using the JavaScript fallback, which follows the same keyword-mode pipeline without embeddings.
5. Shared configuration in `config/engine.json` defines ranking weights, query rules, product types and shopper profiles.
6. Both engines use the processed catalog at `data/processed/catalog.json`.

The parity tests verify that both implementations produce identical rankings, scores and explanations for the same keyword-mode requests.

---

## Quality

`python -m scripts.evaluate` on 32 rule-labelled queries (k = 10, full catalog):

| System | Precision@10 | nDCG@10 | MRR | Results over budget | p95 latency |
|---|---:|---:|---:|---:|---:|
| dense-only (embeddings, no ranking) | 0.875 | 0.953 | 0.954 | 8 | 71 ms |
| lexical (the web fallback) | 0.881 | 0.941 | 0.896 | 0 | 93 ms |
| **hybrid (the Python API)** | **0.969** | **0.996** | **1.000** | **0** | 107 ms |

### How to interpret these results

Labels are regex rules on product name and price (`eval/queries.json`), written independently of the engine's own product-type patterns. They check that results are the right kind of product within budget. They are not human relevance judgements. Latency measured on a 6-core laptop CPU.

Full per-query results: [results/evaluation_report.md](results/evaluation_report.md).

---

## Quick start

Requirements: **Python 3.11+** (tested on 3.13), **Node.js 20+** (tested on 22).

### 1. Start the Python API — semantic engine

```bash
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements-dev.txt
python -m scripts.build_index     # encodes the catalog once: ~5–8 min on CPU, downloads ~90 MB model
uvicorn api_server:app --port 8000
```

The index command encodes the catalog once. It takes approximately 5–8 minutes on CPU and downloads a model of approximately 90 MB.

### 2. Start the web app — another terminal

```bash
npm install
echo BACKEND_URL=http://127.0.0.1:8000 > .env.local
npm run build && npm start        # http://localhost:3000   (or: npm run dev)
```

Open the web app at <http://localhost:3000>.

Without step 1 (or without `BACKEND_URL`), the web app still works using the keyword engine.

---

## Other entry points

### Command-line interface

```bash
python run_pipeline.py "wireless earbuds under 2000" --profile student   # CLI
```

### Analyst console

```bash
pip install -r requirements-dashboard.txt && streamlit run app.py         # analyst console
```

### Full stack with Docker Compose

```bash
docker compose up --build                                                 # full stack on :3000
```

---

## Tests and checks

Run the following commands to test the Python engine, JavaScript fallback, API contract, and formatting.

```bash
pytest                 # 65 tests: parser, ranking, engine, API contract, JS/Python parity, real model
pytest -m "not model"  # skip the tests that load the real embedding model
npm test               # 17 tests: JS engine + Next.js API routes (incl. backend fallback)
npm run lint
ruff check . && ruff format --check src tests api_server.py
python -m scripts.evaluate
```

### Test coverage

| Check | What it covers |
|---|---|
| `pytest` | 65 tests covering parser, ranking, engine, API contract, JavaScript/Python parity and real model |
| `pytest -m "not model"` | Runs the Python tests while skipping tests that load the real embedding model |
| `npm test` | 17 tests covering the JavaScript engine and Next.js API routes, including backend fallback |
| `npm run lint` | Next.js application linting |
| `ruff check .` | Python linting |
| `ruff format --check src tests api_server.py` | Python formatting verification |
| `python -m scripts.evaluate` | Re-runs the recommendation evaluation |

---

## API endpoints

The Next.js application exposes these routes:

| Endpoint | Purpose |
|---|---|
| `/api/recommend` | Product recommendation queries |
| `/api/similar` | Similar-item recommendations |
| `/api/catalog` | Catalog access |
| `/api/health` | Web application health endpoint |

The Python API is served by FastAPI through `api_server.py`.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness |
| `GET /api/ready` | Readiness; returns `503` while loading |

**Backend behavior:** setting `BACKEND_URL` enables semantic search through the Python API. When the backend URL is unset or unreachable, or when the web backend request times out, the web application can answer using the keyword engine according to its fallback configuration.

---

## Configuration

All settings are documented in [`.env.example`](.env.example). **No secrets are required.**

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

See [`.env.example`](.env.example). No secrets are required.

---

## Deployment

### Web on Vercel

Import the repository (framework: Next.js). The catalog and config ship with the functions (`outputFileTracingIncludes` in `next.config.mjs`). Set `BACKEND_URL` to enable semantic search.

### Python API

Deploy on any container host with **≥ 1 GB RAM** (Render, Railway, Fly.io, Cloud Run, a VM):

```bash
docker build -t rec-engine-api .
```

The image bakes in the model and the embeddings, so it starts offline in about 30–40 s.

Health endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness |
| `GET /api/ready` | Readiness, `503` while loading |

Run one replica per ~1 GB. The rate limiter is per-process, so put a gateway limiter in front for multi-replica setups.

### Rollback

Both services are stateless. Redeploy the previous image or commit. A catalog change ships as a new `catalog.json`, and the API rebuilds embeddings when the catalog hash changes.

---

## Data pipeline

The data pipeline has two main steps: build a product catalog and then build its embedding index.

### 1. Build the catalog

```bash
python -m scripts.build_catalog   # data/raw/Amazon-Products.csv  ->  data/processed/catalog.json + catalog_meta.json
```

`build_catalog` keeps listings with a price and at least 20 ratings, collapses colour and size variants, balances departments, and guarantees coverage of every product type the parser understands.

The raw export (`data/raw/`, ~1.8 GB) is not committed.

### 2. Build the embedding index

```bash
python -m scripts.build_index     # catalog.json  ->  models/embeddings.npy + models/manifest.json
```

`models/manifest.json` records the catalog hash, so stale embeddings are detected and never silently served.

---

## Project layout

```text
api_server.py                 FastAPI app (validation, readiness, rate limit, request IDs)
src/                          Python engine: query_parser, lexical (BM25), embeddings, vector_store (FAISS),
                              ranking, personalization, explainer, recommender (orchestrator), catalog
lib/engine/                   JavaScript keyword engine (mirror of the Python lexical mode)
lib/server/                   Next.js request validation and backend client
pages/, components/, styles/  Next.js UI and API routes
config/engine.json            shared ranking weights, query rules, product types, profiles
scripts/                      build_catalog, build_index, evaluate, js_engine_cli (parity tests)
tests/                        pytest suites, tests/js (node:test), shared fixtures
eval/queries.json             evaluation queries and relevance rules
app.py, run_pipeline.py       Streamlit analyst console, CLI
```

### Shared configuration and catalog

| Path | Purpose |
|---|---|
| `config/engine.json` | Shared weights, query rules, product types and shopper profiles |
| `data/processed/catalog.json` | Processed product catalog, built by `scripts/build_catalog.py` |
| `docs/system_design.md` | Pipeline, scoring formula and trade-offs |
| `results/evaluation_report.md` | Full per-query evaluation results |
| `eval/queries.json` | Evaluation queries and relevance rules |
| `tests/test_parity.py` | Identical rankings, scores and explanations between both engines' keyword mode |
| `models/manifest.json` | Catalog hash for detecting stale embeddings |

---

## Known limitations

- The catalog is a **2023 snapshot**: prices, ratings and availability are not live, and there is no stock data.
- The source export has **few laptops** (~85 listings match the laptop type), so laptop results are thin compared to audio, TVs or fashion.
- Personalisation uses **declared profiles**, not behaviour. There is no user history, click feedback or collaborative filtering yet.
- Relevance labels are rule-based (silver standard). There are no human-judged or online (A/B) metrics.
- Product images are hot-linked from Amazon's public CDN and may disappear.

---

## Author

**Omjee R Giri**

---

<div align="center">

*Independent portfolio project. Not affiliated with Amazon.*

</div>
