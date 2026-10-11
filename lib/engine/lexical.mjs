// BM25 keyword index with idf-weighted term coverage. Mirrors src/lexical.py.

import { tokenize } from "./text.mjs";

export class LexicalIndex {
  constructor(documents, phraseMap, { k1 = 1.2, b = 0.75 } = {}) {
    const nDocs = documents.length;
    const postings = new Map(); // term -> { ids: number[], tf: number[] }
    const lengths = new Float64Array(nDocs);
    documents.forEach((text, docId) => {
      const tokens = tokenize(text, phraseMap);
      lengths[docId] = tokens.length;
      const counts = new Map();
      for (const token of tokens) counts.set(token, (counts.get(token) || 0) + 1);
      for (const [token, tf] of counts) {
        let entry = postings.get(token);
        if (!entry) {
          entry = { ids: [], tf: [] };
          postings.set(token, entry);
        }
        entry.ids.push(docId);
        entry.tf.push(tf);
      }
    });

    let total = 0;
    for (let i = 0; i < nDocs; i++) total += lengths[i];
    const avgLen = nDocs ? total / nDocs : 0;

    this.nDocs = nDocs;
    this.maxIdf = Math.log(1 + (nDocs + 0.5) / 0.5);
    this.terms = new Map();
    for (const [token, { ids, tf }] of postings) {
      const df = ids.length;
      const idf = Math.log(1 + (nDocs - df + 0.5) / (df + 0.5));
      const weights = new Float64Array(df);
      for (let j = 0; j < df; j++) {
        const norm = k1 * (1 - b + (b * lengths[ids[j]]) / (avgLen || 1));
        weights[j] = (idf * tf[j] * (k1 + 1)) / (tf[j] + norm);
      }
      this.terms.set(token, { ids: Int32Array.from(ids), weights, idf });
    }
  }

  termIdf(term) {
    const entry = this.terms.get(term);
    return entry ? entry.idf : this.maxIdf;
  }

  bm25(terms) {
    const scores = new Float64Array(this.nDocs);
    for (const term of terms) {
      const entry = this.terms.get(term);
      if (!entry) continue;
      for (let j = 0; j < entry.ids.length; j++) scores[entry.ids[j]] += entry.weights[j];
    }
    return scores;
  }

  presence(term) {
    const mask = new Uint8Array(this.nDocs);
    const entry = this.terms.get(term);
    if (entry) for (const id of entry.ids) mask[id] = 1;
    return mask;
  }

  matched(terms, docIds) {
    const present = terms.filter((t) => this.terms.has(t));
    const masks = present.map((t) => this.presence(t));
    return docIds.map((id) => present.filter((_, k) => masks[k][id] === 1));
  }

  // idf-weighted fraction of `terms` found in each document (plus any terms in `satisfied`).
  coverage(terms, docIds, satisfied = null) {
    if (!terms.length) return docIds.map(() => 0);
    const idf = new Map(terms.map((t) => [t, this.termIdf(t)]));
    let total = 0;
    for (const t of terms) total += idf.get(t);
    const matched = this.matched(terms, docIds);
    return docIds.map((_, k) => {
      const covered = new Set(matched[k]);
      if (satisfied) for (const t of satisfied[k]) covered.add(t);
      let sum = 0;
      for (const t of terms) if (covered.has(t)) sum += idf.get(t);
      return sum / total;
    });
  }
}
