// Keyword ("lexical") recommendation engine used when the Python semantic backend is not
// configured or not reachable. It runs the same pipeline as src/recommender.py without the
// dense-embedding component; tests/test_parity.py checks both produce identical rankings.

import { Catalog } from "./catalog.mjs";
import { explain } from "./explainer.mjs";
import { LexicalIndex } from "./lexical.mjs";
import { cheapness, matchedKeywords, profileSignal } from "./personalization.mjs";
import { parseQuery, productMatchesIntent } from "./queryParser.mjs";
import { combine, compareRanked, dealSignal, popularitySignal, qualitySignal, round6 } from "./ranking.mjs";
import { queryTerms } from "./text.mjs";

export class UnknownProductError extends Error {}
export class InvalidRequestError extends Error {}

const tightest = (pick, ...values) => {
  const present = values.filter((v) => v !== null && v !== undefined);
  return present.length ? pick(...present) : null;
};

function topPositive(scores, ids, n) {
  return ids
    .filter((i) => scores[i] > 0)
    .sort((a, b) => scores[b] - scores[a] || a - b)
    .slice(0, n);
}

export class LexicalEngine {
  constructor(catalogPayload, config, { notice = null } = {}) {
    this.config = config;
    this.catalog = new Catalog(catalogPayload, config);
    this.notice = notice;
    this.lexical = new LexicalIndex(
      Array.from({ length: this.catalog.length }, (_, i) => this.catalog.indexText(i)),
      this.catalog.phraseMap,
      config.bm25,
    );
    this.intentCache = new Map();
    this.stopwords = new Set(config.text.stopwords);
  }

  status() {
    return {
      mode: "lexical",
      model: null,
      degraded: this.notice !== null,
      notice: this.notice,
      products: this.catalog.length,
    };
  }

  intentMask(intentId) {
    if (!this.intentCache.has(intentId)) {
      const spec = this.config.intents[intentId];
      this.intentCache.set(
        intentId,
        Uint8Array.from(this.catalog.normalizedNames, (name) => (productMatchesIntent(name, spec) ? 1 : 0)),
      );
    }
    return this.intentCache.get(intentId);
  }

  allowedIds(filters) {
    const c = this.catalog;
    const ids = [];
    for (let i = 0; i < c.length; i++) {
      if (filters.min_price !== null && c.price[i] < filters.min_price) continue;
      if (filters.max_price !== null && c.price[i] > filters.max_price) continue;
      if (filters.min_rating !== null && c.rating[i] < filters.min_rating) continue;
      if (filters.department && c.mainCategories[i] !== filters.department) continue;
      ids.push(i);
    }
    return ids;
  }

  recommend(query, { profile = "general", topK = 10, filters = {} } = {}) {
    const started = performance.now();
    const cfg = this.config;
    if (!Object.hasOwn(cfg.profiles, profile)) {
      throw new InvalidRequestError(`Unknown profile '${profile}'. Choose one of: ${Object.keys(cfg.profiles).join(", ")}.`);
    }
    const parsed = parseQuery(query, cfg);
    const budget = parsed.budget;
    const effective = {
      department: filters.department ?? null,
      min_rating: filters.min_rating ?? null,
      min_price: tightest(Math.max, filters.min_price, budget?.min),
      max_price: tightest(Math.min, filters.max_price, budget?.max),
    };
    const response = {
      query: parsed.query,
      profile,
      engine: this.status(),
      interpretation: {
        terms: parsed.terms,
        intent: parsed.intent,
        budget,
        prefers_low_price: parsed.prefers_low_price,
      },
      filters: Object.fromEntries(Object.entries(effective).filter(([, v]) => v !== null)),
      total_matches: 0,
      results: [],
    };
    const finish = () => {
      response.took_ms = Math.round((performance.now() - started) * 10) / 10;
      return response;
    };
    if (!parsed.terms.length && parsed.intent === null) {
      response.message = "Tell us what you are looking for, e.g. “wireless earbuds under 2000”.";
      return finish();
    }

    const allowed = this.allowedIds(effective);
    const retrieval = cfg.retrieval;
    const bm25 = this.lexical.bm25(parsed.terms);
    const pool = new Set(topPositive(bm25, allowed, retrieval.lexical_candidates));
    if (parsed.intent) {
      const mask = this.intentMask(parsed.intent.id);
      let intentIds = allowed.filter((i) => mask[i] === 1);
      if (intentIds.length > retrieval.max_intent_candidates) {
        const count = this.catalog.ratingCount;
        intentIds = intentIds
          .sort((a, b) => bm25[b] - bm25[a] || count[b] - count[a] || a - b)
          .slice(0, retrieval.max_intent_candidates);
      }
      for (const i of intentIds) pool.add(i);
    }
    const candidates = [...pool].sort((a, b) => a - b);
    if (!candidates.length) return finish();

    // ---- relevance
    const relCfg = cfg.relevance;
    const mask = parsed.intent ? this.intentMask(parsed.intent.id) : null;
    const intentHits = candidates.map((i) => (mask ? mask[i] === 1 : false));
    const intentTerms = parsed.intent ? new Set(queryTerms(parsed.intent.keyword, new Set())) : new Set();
    const satisfied = intentHits.map((hit) => (hit ? intentTerms : new Set()));
    const coverage = this.lexical.coverage(parsed.terms, candidates, satisfied);
    const relevance = coverage.slice();
    if (parsed.intent && intentHits.some(Boolean)) {
      for (let k = 0; k < relevance.length; k++) if (!intentHits[k]) relevance[k] *= 1 - relCfg.intent_mismatch_penalty;
    }

    const keptIdx = [];
    for (let k = 0; k < candidates.length; k++) if (relevance[k] >= relCfg.min_relevance) keptIdx.push(k);
    response.total_matches = keptIdx.length;
    if (!keptIdx.length) return finish();
    const kept = keptIdx.map((k) => candidates[k]);
    const matched = this.lexical.matched(parsed.terms, kept);

    // ---- ranking
    const c = this.catalog;
    const profileCfg = cfg.profiles[profile];
    const prefersLow = parsed.prefers_low_price || Boolean(profileCfg.prefers_low_price);
    const cheapValues = prefersLow ? cheapness(kept.map((i) => c.price[i])) : null;
    const scored = kept.map((i, k) => {
      const hits = matchedKeywords(c.normalizedNames[i], profileCfg);
      const cheap = cheapValues ? cheapValues[k] : 0;
      const signals = {
        relevance: relevance[keptIdx[k]],
        quality: qualitySignal(c.rating[i], c.ratingCount[i], cfg.quality),
        popularity: popularitySignal(c.ratingCount[i], cfg.popularity),
        deal: dealSignal(c.price[i], c.listPrice[i]),
        profile: profileSignal(hits.length, cheap, profileCfg, parsed.prefers_low_price),
      };
      const { score, contributions } = combine(signals, cfg.weights);
      return { k, i, score, signals, contributions, hits, cheap, ratingCount: c.ratingCount[i], asin: c.asins[i] };
    });
    scored.sort(compareRanked);

    const seen = new Set();
    for (const row of scored) {
      const keys = c.variantKeys(row.i, retrieval.dedupe_tokens);
      if (keys.some((key) => seen.has(key))) continue;
      keys.forEach((key) => seen.add(key));
      const item = c.record(row.i);
      const k = row.k;
      Object.assign(item, {
        score: round6(row.score),
        signals: {
          ...Object.fromEntries(Object.entries(row.signals).map(([n, v]) => [n, round6(v)])),
          lexical: round6(coverage[keptIdx[k]]),
          semantic: null,
          cosine: null,
        },
        contributions: Object.fromEntries(Object.entries(row.contributions).map(([n, v]) => [n, round6(v)])),
        matched_terms: matched[k],
        intent_match: intentHits[keptIdx[k]],
        profile_keywords: row.hits,
        reasons: explain(item, {
          matchedTerms: matched[k],
          semantic: null,
          intent: parsed.intent,
          intentMatch: intentHits[keptIdx[k]],
          budget,
          profileId: profile,
          profile: profileCfg,
          profileHits: row.hits,
          cheap: prefersLow ? row.cheap : null,
        }),
      });
      response.results.push(item);
      if (response.results.length >= topK) break;
    }
    return finish();
  }

  similar(asin, k = 8) {
    const started = performance.now();
    const c = this.catalog;
    if (!c.position.has(asin)) throw new UnknownProductError(asin);
    const source = c.position.get(asin);
    const simCfg = this.config.similar;
    const n = simCfg.candidates + 1;
    const terms = queryTerms(c.normalizedNames[source], this.stopwords);
    const bm25 = this.lexical.bm25(terms);
    const ids = topPositive(
      bm25,
      Array.from({ length: c.length }, (_, i) => i),
      n,
    );
    const top = ids.length ? Math.max(...ids.map((i) => bm25[i])) : 0;
    const weights = simCfg.weights;
    const rows = [];
    for (const i of ids) {
      if (i === source || top <= 0) continue;
      const sim = bm25[i] / top;
      const sameSub = c.subCategories[i] === c.subCategories[source] ? 1 : 0;
      const score =
        weights.similarity * sim +
        weights.subcategory * sameSub +
        weights.quality * qualitySignal(c.rating[i], c.ratingCount[i], this.config.quality) +
        weights.popularity * popularitySignal(c.ratingCount[i], this.config.popularity);
      rows.push({ i, score, sim, ratingCount: c.ratingCount[i], asin: c.asins[i] });
    }
    rows.sort(compareRanked);
    const tokens = this.config.retrieval.dedupe_tokens;
    const seen = new Set(c.variantKeys(source, tokens));
    const results = [];
    for (const row of rows) {
      const keys = c.variantKeys(row.i, tokens);
      if (keys.some((key) => seen.has(key))) continue;
      keys.forEach((key) => seen.add(key));
      results.push({ ...c.record(row.i), score: round6(row.score), similarity: round6(row.sim) });
      if (results.length >= k) break;
    }
    return {
      product: c.record(source),
      engine: this.status(),
      results,
      took_ms: Math.round((performance.now() - started) * 10) / 10,
    };
  }
}
