"""Recommendation engine: query understanding -> hybrid retrieval -> multi-signal ranking.

Pipeline for `recommend()`:
  1. parse the query (budget, product-type intent, search terms)
  2. apply hard filters (budget, department, minimum rating)
  3. build a candidate pool: BM25 top-N  ∪  dense top-N (FAISS)  ∪  products of the intent
  4. relevance = blend of semantic similarity and idf-weighted term coverage, with
     products outside the requested product type down-weighted
  5. score = weighted relevance, rating quality, popularity, discount and profile fit
  6. collapse near-duplicate variants and explain each result from its signals

With no embedding model available the engine runs the same pipeline without the dense
component ("lexical" mode) — the mode the JavaScript fallback in lib/engine reproduces.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from . import embeddings as emb
from .catalog import Catalog, load_catalog
from .config import Settings, load_engine_config
from .explainer import explain
from .lexical import LexicalIndex
from .personalization import cheapness, matched_keywords, profile_signal
from .query_parser import parse_query, product_matches_intent
from .ranking import (
    combine,
    deal_signal,
    dense_relevance,
    popularity_signal,
    quality_signal,
    sort_key,
)
from .text import query_terms
from .vector_store import VectorIndex

log = logging.getLogger(__name__)


class UnknownProductError(KeyError):
    pass


def _tightest(pick, *values: float | None) -> float | None:
    present = [v for v in values if v is not None]
    return pick(present) if present else None


@dataclass
class Filters:
    department: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    min_rating: float | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class DenseComponent:
    encoder: emb.Encoder
    index: VectorIndex


class RecommendationEngine:
    def __init__(self, catalog: Catalog, config: dict, dense: DenseComponent | None = None, notice: str | None = None):
        self.catalog = catalog
        self.config = config
        self.dense = dense
        self.notice = notice
        self.lexical = LexicalIndex(
            [catalog.index_text(i) for i in range(len(catalog))],
            catalog.phrase_map,
            k1=config["bm25"]["k1"],
            b=config["bm25"]["b"],
        )
        self._departments = np.asarray(catalog.main_categories, dtype=object)
        self._intent_cache: dict[str, np.ndarray] = {}

    # ------------------------------------------------------------------ loading

    @classmethod
    def load(
        cls,
        settings: Settings,
        encoder_factory: Callable[[str], emb.Encoder] | None = emb.SentenceTransformerEncoder,
        config: dict | None = None,
    ) -> RecommendationEngine:
        config = config or load_engine_config()
        catalog = load_catalog(settings.catalog_path, config)
        log.info("Loaded catalog: %d products (sha256 %s…)", len(catalog), catalog.sha256[:12])
        dense, notice = None, None
        if encoder_factory is None:
            notice = "Semantic search disabled by configuration; using keyword ranking."
        else:
            try:
                dense = cls._load_dense(catalog, settings, encoder_factory)
            except Exception as exc:  # model download failures, corrupt artifacts, OOM...
                if not settings.allow_lexical_fallback:
                    raise
                log.exception("Semantic search unavailable; falling back to keyword ranking")
                notice = f"Semantic search unavailable ({type(exc).__name__}); results use keyword ranking."
        engine = cls(catalog, config, dense=dense, notice=notice)
        engine.warm_up()
        return engine

    @staticmethod
    def _load_dense(catalog: Catalog, settings: Settings, encoder_factory) -> DenseComponent:
        encoder = encoder_factory(settings.embedding_model)
        try:
            vectors = emb.load_embeddings(
                catalog, settings.embedding_model, settings.embeddings_path, settings.manifest_path
            )
        except emb.StaleEmbeddingsError as exc:
            if not settings.auto_build_index:
                raise
            log.warning("%s Rebuilding embeddings (AUTO_BUILD_INDEX=true).", exc)
            vectors = emb.build_embeddings(catalog, encoder)
            emb.save_embeddings(
                vectors, catalog, settings.embedding_model, settings.embeddings_path, settings.manifest_path
            )
        return DenseComponent(encoder=encoder, index=VectorIndex(vectors))

    # ------------------------------------------------------------------ status

    @property
    def mode(self) -> str:
        return "hybrid" if self.dense is not None else "lexical"

    def status(self) -> dict:
        return {
            "mode": self.mode,
            "model": self.dense.encoder.name if self.dense else None,
            "degraded": self.notice is not None,
            "notice": self.notice,
            "products": len(self.catalog),
            "catalog_sha256": self.catalog.sha256,
        }

    def profiles(self) -> dict:
        return {
            pid: {"label": p["label"], "description": p["description"]} for pid, p in self.config["profiles"].items()
        }

    # ------------------------------------------------------------------ helpers

    def warm_up(self) -> None:
        """Precompute product-type masks so no request pays for them (~2s for the full catalog)."""
        for intent_id in self.config["intents"]:
            self.intent_mask(intent_id)

    def intent_mask(self, intent_id: str) -> np.ndarray:
        if intent_id not in self._intent_cache:
            spec = self.config["intents"][intent_id]
            self._intent_cache[intent_id] = np.fromiter(
                (product_matches_intent(name, spec) for name in self.catalog.normalized_names),
                dtype=bool,
                count=len(self.catalog),
            )
        return self._intent_cache[intent_id]

    def _allowed(self, filters: Filters) -> np.ndarray:
        c = self.catalog
        mask = np.ones(len(c), dtype=bool)
        if filters.min_price is not None:
            mask &= c.price >= filters.min_price
        if filters.max_price is not None:
            mask &= c.price <= filters.max_price
        if filters.min_rating is not None:
            mask &= c.rating >= filters.min_rating
        if filters.department:
            mask &= self._departments == filters.department
        return mask

    @staticmethod
    def _top(scores: np.ndarray, ids: np.ndarray, n: int) -> np.ndarray:
        """Ids of the n highest positive scores; ties broken by lower id."""
        positive = ids[scores[ids] > 0]
        order = np.lexsort((positive, -scores[positive]))
        return positive[order[:n]]

    # ------------------------------------------------------------------ recommend

    def recommend(
        self,
        query: str,
        profile: str = "general",
        top_k: int = 10,
        filters: Filters | None = None,
        use_dense: bool = True,
    ) -> dict:
        started = time.perf_counter()
        cfg = self.config
        if profile not in cfg["profiles"]:
            raise ValueError(f"Unknown profile '{profile}'. Choose one of: {', '.join(cfg['profiles'])}.")
        filters = filters or Filters()
        parsed = parse_query(query, cfg)
        budget = parsed.budget
        effective = Filters(
            department=filters.department,
            min_rating=filters.min_rating,
            min_price=_tightest(max, filters.min_price, budget.min if budget else None),
            max_price=_tightest(min, filters.max_price, budget.max if budget else None),
        )
        dense = self.dense if use_dense else None
        response = {
            "query": parsed.query,
            "profile": profile,
            "engine": {**self.status(), "mode": "hybrid" if dense else "lexical"},
            "interpretation": {
                "terms": parsed.terms,
                "intent": parsed.intent.__dict__ if parsed.intent else None,
                "budget": budget.__dict__ if budget else None,
                "prefers_low_price": parsed.prefers_low_price,
            },
            "filters": effective.to_dict(),
            "total_matches": 0,
            "results": [],
        }
        if not parsed.terms and parsed.intent is None:
            response["message"] = "Tell us what you are looking for, e.g. “wireless earbuds under 2000”."
            response["took_ms"] = round((time.perf_counter() - started) * 1000, 1)
            return response

        allowed = self._allowed(effective)
        allowed_ids = np.flatnonzero(allowed)
        retrieval = cfg["retrieval"]

        bm25 = self.lexical.bm25(parsed.terms)
        pool = [self._top(bm25, allowed_ids, retrieval["lexical_candidates"])]
        query_vector = None
        if dense is not None:
            query_vector = dense.encoder.encode([parsed.search_text or parsed.query])[0]
            dense_ids, _ = dense.index.search(
                query_vector, retrieval["dense_candidates"], None if allowed.all() else allowed_ids
            )
            pool.append(dense_ids.astype(np.int64))
        intent_ids = None
        if parsed.intent is not None:
            intent_ids = allowed_ids[self.intent_mask(parsed.intent.id)[allowed_ids]]
            if len(intent_ids) > retrieval["max_intent_candidates"]:
                order = np.lexsort((intent_ids, -self.catalog.rating_count[intent_ids], -bm25[intent_ids]))
                intent_ids = intent_ids[order[: retrieval["max_intent_candidates"]]]
            pool.append(intent_ids)
        candidates = np.unique(np.concatenate(pool)) if pool else np.empty(0, dtype=np.int64)
        if len(candidates) == 0:
            response["took_ms"] = round((time.perf_counter() - started) * 1000, 1)
            return response

        # ---- relevance
        rel_cfg = cfg["relevance"]
        intent_hits = (
            self.intent_mask(parsed.intent.id)[candidates] if parsed.intent else np.zeros(len(candidates), bool)
        )
        intent_terms = set(query_terms(parsed.intent.keyword, frozenset())) if parsed.intent else set()
        satisfied = [intent_terms if hit else set() for hit in intent_hits]
        coverage = self.lexical.coverage(parsed.terms, candidates, satisfied)
        semantic = cosines = None
        if dense is not None:
            cosines = dense.index.similarity(query_vector, candidates)
            semantic = np.array([dense_relevance(float(c), rel_cfg) for c in cosines])
            relevance = rel_cfg["dense_weight"] * semantic + rel_cfg["lexical_weight"] * coverage
        else:
            relevance = coverage.copy()
        if parsed.intent is not None and intent_hits.any():
            relevance[~intent_hits] *= 1.0 - rel_cfg["intent_mismatch_penalty"]

        keep = relevance >= rel_cfg["min_relevance"]
        kept = candidates[keep]
        response["total_matches"] = int(len(kept))
        if len(kept) == 0:
            response["took_ms"] = round((time.perf_counter() - started) * 1000, 1)
            return response
        kept_relevance = relevance[keep]
        kept_coverage = coverage[keep]
        kept_semantic = semantic[keep] if semantic is not None else None
        kept_cosine = cosines[keep] if cosines is not None else None
        kept_intent = intent_hits[keep]
        matched = self.lexical.matched(parsed.terms, kept)

        # ---- ranking
        profile_cfg = cfg["profiles"][profile]
        prefers_low = parsed.prefers_low_price or bool(profile_cfg.get("prefers_low_price"))
        cheap_values = cheapness([float(p) for p in self.catalog.price[kept]]) if prefers_low else None
        c = self.catalog
        scored = []
        for k, i in enumerate(kept):
            hits = matched_keywords(c.normalized_names[i], profile_cfg)
            cheap = cheap_values[k] if cheap_values is not None else 0.0
            signals = {
                "relevance": float(kept_relevance[k]),
                "quality": quality_signal(float(c.rating[i]), float(c.rating_count[i]), cfg["quality"]),
                "popularity": popularity_signal(float(c.rating_count[i]), cfg["popularity"]),
                "deal": deal_signal(float(c.price[i]), float(c.list_price[i])),
                "profile": profile_signal(len(hits), cheap, profile_cfg, parsed.prefers_low_price),
            }
            score, contributions = combine(signals, cfg["weights"])
            scored.append(
                (
                    sort_key(score, float(c.rating_count[i]), c.asins[i]),
                    k,
                    int(i),
                    score,
                    signals,
                    contributions,
                    hits,
                    cheap,
                )
            )
        scored.sort(key=lambda row: row[0])

        results, seen = [], set()
        for _, k, i, score, signals, contributions, hits, cheap in scored:
            keys = c.variant_keys(i, retrieval["dedupe_tokens"])
            if seen.intersection(keys):
                continue
            seen.update(keys)
            item = c.record(i)
            sem = float(kept_semantic[k]) if kept_semantic is not None else None
            cos = float(kept_cosine[k]) if kept_cosine is not None else None
            item.update(
                {
                    "score": round(score, 6),
                    "signals": {
                        **{name: round(v, 6) for name, v in signals.items()},
                        "lexical": round(float(kept_coverage[k]), 6),
                        "semantic": round(sem, 6) if sem is not None else None,
                        "cosine": round(cos, 6) if cos is not None else None,
                    },
                    "contributions": {name: round(v, 6) for name, v in contributions.items()},
                    "matched_terms": matched[k],
                    "intent_match": bool(kept_intent[k]),
                    "profile_keywords": hits,
                    "reasons": explain(
                        item,
                        matched_terms=matched[k],
                        semantic=sem,
                        cosine=cos,
                        intent=response["interpretation"]["intent"],
                        intent_match=bool(kept_intent[k]),
                        budget=response["interpretation"]["budget"],
                        profile_id=profile,
                        profile=profile_cfg,
                        profile_hits=hits,
                        cheap=cheap if prefers_low else None,
                    ),
                }
            )
            results.append(item)
            if len(results) >= top_k:
                break

        response["results"] = results
        response["took_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return response

    # ------------------------------------------------------------------ similar items

    def similar(self, asin: str, k: int = 8) -> dict:
        started = time.perf_counter()
        c = self.catalog
        if asin not in c.position:
            raise UnknownProductError(asin)
        source = c.position[asin]
        sim_cfg = self.config["similar"]
        n = sim_cfg["candidates"] + 1

        if self.dense is not None:
            ids, scores = self.dense.index.search(self.dense.index.vectors[source], n)
            similarity = {int(i): max(0.0, float(s)) for i, s in zip(ids, scores, strict=True)}
        else:
            terms = query_terms(c.normalized_names[source], frozenset(self.config["text"]["stopwords"]))
            bm25 = self.lexical.bm25(terms)
            ids = self._top(bm25, np.arange(len(c)), n)
            top = float(bm25[ids].max()) if len(ids) else 0.0
            similarity = {int(i): float(bm25[i]) / top for i in ids} if top > 0 else {}

        weights = sim_cfg["weights"]
        rows = []
        for i, sim in similarity.items():
            if i == source:
                continue
            same_sub = 1.0 if c.sub_categories[i] == c.sub_categories[source] else 0.0
            score = (
                weights["similarity"] * sim
                + weights["subcategory"] * same_sub
                + weights["quality"]
                * quality_signal(float(c.rating[i]), float(c.rating_count[i]), self.config["quality"])
                + weights["popularity"] * popularity_signal(float(c.rating_count[i]), self.config["popularity"])
            )
            rows.append((sort_key(score, float(c.rating_count[i]), c.asins[i]), i, score, sim))
        rows.sort(key=lambda row: row[0])

        tokens = self.config["retrieval"]["dedupe_tokens"]
        results, seen = [], set(c.variant_keys(source, tokens))
        for _, i, score, sim in rows:
            keys = c.variant_keys(i, tokens)
            if seen.intersection(keys):
                continue
            seen.update(keys)
            results.append({**c.record(i), "score": round(score, 6), "similarity": round(sim, 6)})
            if len(results) >= k:
                break
        return {
            "product": c.record(source),
            "engine": self.status(),
            "results": results,
            "took_ms": round((time.perf_counter() - started) * 1000, 1),
        }
