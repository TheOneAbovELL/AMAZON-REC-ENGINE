"""BM25 keyword index with idf-weighted term coverage.

BM25 decides which products enter the candidate pool; *coverage* (the idf-weighted share
of query terms a product contains) is the bounded, interpretable relevance signal used for
ranking. Mirrored by lib/engine/lexical.mjs.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import sparse

from .text import tokenize


class LexicalIndex:
    def __init__(self, documents: list[str], phrase_map: dict, k1: float = 1.2, b: float = 0.75):
        self.phrase_map = phrase_map
        vocab: dict[str, int] = {}
        rows, cols, tfs = [], [], []
        lengths = np.zeros(len(documents), dtype=np.float64)
        for doc_id, text in enumerate(documents):
            tokens = tokenize(text, phrase_map)
            lengths[doc_id] = len(tokens)
            counts: dict[int, int] = {}
            for token in tokens:
                term_id = vocab.setdefault(token, len(vocab))
                counts[term_id] = counts.get(term_id, 0) + 1
            for term_id, tf in counts.items():
                rows.append(doc_id)
                cols.append(term_id)
                tfs.append(tf)

        n_docs = len(documents)
        tf = np.asarray(tfs, dtype=np.float64)
        rows_arr = np.asarray(rows, dtype=np.int64)
        cols_arr = np.asarray(cols, dtype=np.int64)
        doc_freq = np.bincount(cols_arr, minlength=len(vocab)).astype(np.float64)
        self.idf = np.log(1.0 + (n_docs - doc_freq + 0.5) / (doc_freq + 0.5))
        self.max_idf = math.log(1.0 + (n_docs + 0.5) / 0.5)
        avg_len = float(lengths.mean()) if n_docs else 0.0
        norm = k1 * (1.0 - b + b * lengths[rows_arr] / (avg_len or 1.0))
        weights = self.idf[cols_arr] * tf * (k1 + 1.0) / (tf + norm)

        shape = (n_docs, len(vocab))
        self.vocab = vocab
        self.n_docs = n_docs
        self.weights = sparse.csc_matrix((weights, (rows_arr, cols_arr)), shape=shape)
        # Row-oriented copy: candidate rows are sliced per query.
        self.presence = sparse.csr_matrix((np.ones_like(weights), (rows_arr, cols_arr)), shape=shape)

    def term_idf(self, term: str) -> float:
        term_id = self.vocab.get(term)
        # Terms absent from the catalog are maximally specific: nothing can satisfy them.
        return float(self.idf[term_id]) if term_id is not None else self.max_idf

    def bm25(self, terms: list[str]) -> np.ndarray:
        ids = [self.vocab[t] for t in terms if t in self.vocab]
        if not ids:
            return np.zeros(self.n_docs)
        return np.asarray(self.weights[:, ids].sum(axis=1)).ravel()

    def matched(self, terms: list[str], doc_ids: np.ndarray) -> list[list[str]]:
        """Which query terms each of `doc_ids` contains."""
        present = [t for t in terms if t in self.vocab]
        if not present or len(doc_ids) == 0:
            return [[] for _ in doc_ids]
        block = self.presence[doc_ids][:, [self.vocab[t] for t in present]].toarray() > 0  # (len(doc_ids), terms)
        return [[t for t, hit in zip(present, row, strict=True) if hit] for row in block]

    def coverage(self, terms: list[str], doc_ids: np.ndarray, satisfied: list[set[str]] | None = None) -> np.ndarray:
        """idf-weighted fraction of `terms` found in each document (plus any terms in `satisfied`)."""
        if not terms:
            return np.zeros(len(doc_ids))
        idf = {t: self.term_idf(t) for t in terms}
        total = sum(idf.values())
        matched = self.matched(terms, doc_ids)
        out = np.zeros(len(doc_ids))
        for k, hits in enumerate(matched):
            covered = set(hits)
            if satisfied is not None:
                covered |= satisfied[k]
            out[k] = sum(idf[t] for t in terms if t in covered) / total
        return out
