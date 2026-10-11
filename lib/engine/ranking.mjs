// Ranking signals, each scaled to [0, 1], and the weighted final score. Mirrors src/ranking.py.

export const SIGNALS = ["relevance", "quality", "popularity", "deal", "profile"];

export const clip01 = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);

export function qualitySignal(rating, count, cfg) {
  const smoothed = (count * rating + cfg.prior_count * cfg.prior_rating) / (count + cfg.prior_count);
  return clip01((smoothed - cfg.floor) / (cfg.ceiling - cfg.floor));
}

export function popularitySignal(count, cfg) {
  return clip01(Math.log1p(Math.max(count, 0)) / Math.log1p(cfg.reference_count));
}

export function dealSignal(price, listPrice) {
  if (listPrice <= 0 || price >= listPrice) return 0;
  return clip01((listPrice - price) / listPrice);
}

export function combine(signals, weights) {
  const contributions = {};
  let score = 0;
  for (const name of SIGNALS) {
    contributions[name] = weights[name] * signals[name];
    score += contributions[name];
  }
  return { score, contributions };
}

// Deterministic ordering shared with the Python engine: score, then rating count, then ASIN.
export function compareRanked(a, b) {
  const sa = Number(a.score.toFixed(10));
  const sb = Number(b.score.toFixed(10));
  if (sa !== sb) return sb - sa;
  if (a.ratingCount !== b.ratingCount) return b.ratingCount - a.ratingCount;
  return a.asin < b.asin ? -1 : a.asin > b.asin ? 1 : 0;
}

export const round6 = (v) => Math.round(v * 1e6) / 1e6;
