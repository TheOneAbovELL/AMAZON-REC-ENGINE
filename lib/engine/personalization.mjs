// Shopper-profile signal. Mirrors src/personalization.py.

import { escapeRegex } from "./text.mjs";

export const KEYWORD_SATURATION = 2;

const keywordCache = new WeakMap();
function keywordRegex(profile) {
  if (!keywordCache.has(profile)) {
    const keywords = [...(profile.keywords || [])].sort((a, b) => b.length - a.length);
    keywordCache.set(
      profile,
      keywords.length ? new RegExp(`(?<![a-z0-9])(${keywords.map(escapeRegex).join("|")})(?![a-z0-9])`, "g") : null,
    );
  }
  return keywordCache.get(profile);
}

export function matchedKeywords(normalizedName, profile) {
  const re = keywordRegex(profile);
  if (!re) return [];
  return [...new Set([...normalizedName.matchAll(re)].map((m) => m[1]))];
}

// Share of the other relevant products that cost more than each product.
export function cheapness(prices) {
  const n = prices.length;
  if (n === 1) return [1];
  const ordered = [...prices].sort((a, b) => a - b);
  return prices.map((price) => {
    let lo = 0;
    let hi = n;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (ordered[mid] <= price) lo = mid + 1;
      else hi = mid;
    }
    return (n - lo) / (n - 1);
  });
}

export function profileSignal(keywordHits, cheap, profile, prefersLowPrice) {
  const parts = [];
  if ((profile.keywords || []).length) parts.push(Math.min(1, keywordHits / KEYWORD_SATURATION));
  if (prefersLowPrice || profile.prefers_low_price) parts.push(cheap);
  return parts.length ? parts.reduce((a, b) => a + b, 0) / parts.length : 0;
}
