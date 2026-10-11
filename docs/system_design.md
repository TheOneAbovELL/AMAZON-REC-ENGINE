# System design

## Goal

Return the right *kind* of product, within the shopper's constraints, ranked by evidence the shopper
can inspect. Three properties drive the design:

1. **Constraints are hard.** "Under 90k" means nothing over ₹90,000, and "laptop" does not mean "laptop bag".
2. **Meaning and exact terms both matter.** Embeddings understand "something to keep my tea hot".
   Keywords catch model numbers like "WH-1000XM4" that embeddings blur.
3. **Every score is explainable.** Explanations are generated from the signals that produced the
   ranking, so they cannot claim anything the ranker did not use.

## Pipeline (`src/recommender.py`, mirrored by `lib/engine/engine.mjs`)

```
query ─► parse ─► hard filters ─► candidate pool ─► relevance ─► score ─► de-duplicate ─► explain
```

1. **Parse** (`query_parser.py`): normalise spelling and units ("t-shirt"→"tshirt", "43 inches"→"43inch").
   Then extract the budget, the product-type intent and the search terms.
   - Budgets are read only from explicit phrasing: *under/below/within X*, *between X and Y*,
     *around X* (±20%), *above X*, or amounts carrying ₹/Rs/INR or a k/thousand/lakh suffix. A bare
     number is never a price, so "RTX 4060", "i5 12th gen" and "50 inch" are not budgets.
   - Intent: the product type named **last** wins ("gaming laptop"→laptop, "laptop bag"→bag). If the
     query names one of that type's accessory terms ("laptop stand", "mobile holder"), the intent is
     dropped, because the shopper wants the accessory.
2. **Hard filters**: budget and the UI's department, max price and min rating filters. Listings with no
   price never enter the catalog, so budgets are always checkable.
3. **Candidate pool** = BM25 top 300 ∪ FAISS top 300 (filter-restricted with an ID selector) ∪ products
   matching the intent (up to 4,000).
4. **Relevance** ∈ [0, 1]:
   - keyword coverage = idf-weighted share of query terms in the listing. An intent match satisfies the
     intent's own word, because phone listings rarely say "phone".
   - semantic = cosine similarity mapped linearly from [0.20, 0.70] onto [0, 1]
   - relevance = 0.55·semantic + 0.45·coverage (keyword-only mode: coverage)
   - products of the wrong type are multiplied by 0.5 when the pool contains the right type
   - candidates below 0.12 are dropped, so an unanswerable query returns nothing rather than noise
5. **Score** = 0.62·relevance + 0.14·quality + 0.10·popularity + 0.04·discount + 0.10·profile
   - quality: Bayesian-averaged rating `(n·r + 50·4.0)/(n + 50)`, scaled from 3–5★ onto [0, 1]. A 4.8★
     product with 6 ratings ranks below a 4.5★ product with 5,000.
   - popularity: `log(1+n)/log(1+100,000)`
   - profile: keyword affinity (e.g. "rtx", "144hz" for gamers; saturates at 2 matches), averaged with
     *cheapness* (share of relevant results that cost more) for price-sensitive profiles or "cheap/budget" queries
   - ties break on rating count, then ASIN, identically in both languages
6. **De-duplicate**: colour and size variants are collapsed by their leading title words outside
   brackets, and by the review pool Amazon shares across variants (same brand, rating count and rating).
7. **Explain** (`explainer.py`): one sentence per signal that cleared a threshold.

All weights and rules live in `config/engine.json`, shared by both engines.

## Similar items

Python: FAISS nearest neighbours of the product's own embedding. JavaScript fallback: BM25 using the
product's title as the query. Both re-rank with
`0.75·similarity + 0.10·same sub-category + 0.10·quality + 0.05·popularity` and collapse variants.

## Why these choices

| Decision | Reason |
|---|---|
| Hybrid (dense + BM25) instead of dense only | Evaluation: hybrid P@10 0.969 vs dense-only 0.875. Dense-only also returned 8 over-budget results across the query set. |
| Rule-based query parsing, not an LLM | Budgets and product types must be exact, testable and free per query. An LLM adds latency, cost and failure modes for a deterministic task. |
| Deterministic explanations, not generated text | They are faithful by construction. A generated explanation could cite reasons the ranker never used. |
| FAISS `IndexFlatIP` (exact search) | At 34k × 384 dims exact search takes milliseconds. An approximate index (IVF/HNSW) only pays off at millions of items. |
| float16 embeddings + manifest with catalog SHA-256 | Halves memory and disk. The hash makes a stale index impossible to serve silently. The previous version served a 309-vector index against a 314-row catalog, which shifted every result. |
| Duplicate keyword engine in JS | Lets the Vercel deployment work with no Python host. Drift is prevented by shared config, shared fixtures and a cross-language parity test. |
| all-MiniLM-L6-v2 | 384 dims, ~90 MB, CPU-friendly (~115 products/s to encode, ~20 ms per query). |

## Operational behaviour

- The API loads the engine in a background thread. `/api/health` answers at once, while `/api/ready` and
  `/api/recommend` return 503 with `Retry-After` until the engine is loaded (~35 s).
- The web app falls back to the keyword engine when the API is unconfigured, unreachable, times out
  (8 s) or returns 5xx/429, and the response carries an `engine.notice` that the UI displays. API 4xx
  validation errors are passed through, not masked.
- If the embedding model cannot load, the API degrades to keyword mode (`ALLOW_LEXICAL_FALLBACK`)
  instead of failing.
- Inputs are validated at both layers: query ≤ 200 chars, `top_k` ≤ 50, known profile and department,
  and sane price and rating ranges. Unknown fields are rejected.
- Errors never echo internals to clients. Every API response carries `X-Request-ID`.

## Future work

- Learning-to-rank (e.g. LightGBM LambdaMART) once click or purchase feedback exists. The per-signal
  contributions already returned are natural features.
- Behavioural personalisation and collaborative filtering, which need user events and a persistent store.
- Human-judged relevance labels and online A/B evaluation.
- A refreshed catalog from a live product feed, with stock and current prices.
