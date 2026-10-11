// Deterministic query understanding: budget, product-type intent and search terms.
// Mirrors src/query_parser.py; tests/fixtures/query_cases.json is asserted by both suites.

import { escapeRegex, normalize, queryTerms } from "./text.mjs";

// A number followed by a unit ("50 cm", "1.5 ton", "2 years") is a spec, not a price.
const UNIT_GUARD =
  "(?!\\s*(?:inch|inches|in|cm|mm|gb|tb|hz|mah|mp|w|watt|watts|kg|g|gm|ml|l|ltr|litre|litres|" +
  "liter|liters|ton|tons|star|stars|year|years|month|months|day|days|pcs|pieces|pack|x|" +
  "hour|hours|hr|hrs|people|person|persons)\\b)";
const AMOUNT = "(?:(?:₹|\\brs\\.?|\\binr)\\s*)?(\\d+(?:\\.\\d+)?)\\s*(k|thousand|lakhs?|lacs?)?(?![a-z0-9])" + UNIT_GUARD;
const MARKED_AMOUNT =
  "(?:(?:₹|\\brs\\.?|\\binr)\\s*(\\d+(?:\\.\\d+)?)\\s*(k|thousand|lakhs?|lacs?)?" +
  "|\\b(\\d+(?:\\.\\d+)?)\\s*(k|thousand|lakhs?|lacs?))(?![a-z0-9])";

const RANGE_RE = new RegExp("\\b(?:between|from)\\s+" + AMOUNT + "\\s*(?:and|to|-)\\s*" + AMOUNT);
const MAX_RE = new RegExp(
  "(?:\\b(?:under|below|less than|within|upto|up to|max|maximum|budget of|budget is|budget|" +
    "not more than|cheaper than|lower than)|<=?)\\s*" +
    AMOUNT,
);
const MIN_RE = new RegExp("(?:\\b(?:above|over|more than|at least|minimum|min|starting at|starting)|>=?)\\s*" + AMOUNT);
const AROUND_RE = new RegExp("(?:\\b(?:around|about|approx|approximately|roughly|near)|~)\\s*" + AMOUNT);
const MARKED_RE = new RegExp(MARKED_AMOUNT);
const THOUSANDS_RE = /(?<=\d),(?=\d)/g;
export const MIN_BUDGET = 50;

function amount(number, unit) {
  let value = parseFloat(number);
  const u = (unit || "").toLowerCase();
  if (u === "k" || u === "thousand") value *= 1000;
  else if (u.startsWith("lakh") || u.startsWith("lac")) value *= 100000;
  return value;
}

const strip = (text, match) => text.slice(0, match.index) + " " + text.slice(match.index + match[0].length);

export function parseBudget(normalized) {
  let text = normalized.replace(THOUSANDS_RE, "");
  let low = null;
  let high = null;
  const spans = [];

  let match = RANGE_RE.exec(text);
  if (match) {
    const a = amount(match[1], match[2]);
    const b = amount(match[3], match[4]);
    low = Math.min(a, b);
    high = Math.max(a, b);
    spans.push(match[0].trim());
    text = strip(text, match);
  }

  for (const [regex, kind] of [
    [AROUND_RE, "around"],
    [MAX_RE, "max"],
    [MIN_RE, "min"],
  ]) {
    match = regex.exec(text);
    if (!match) continue;
    const value = amount(match[1], match[2]);
    if (value < MIN_BUDGET) continue;
    if (kind === "around") {
      low = value * 0.8;
      high = value * 1.2;
    } else if (kind === "max") {
      high = high === null ? value : Math.min(high, value);
    } else {
      low = low === null ? value : Math.max(low, value);
    }
    spans.push(match[0].trim());
    text = strip(text, match);
  }

  if (low === null && high === null) {
    match = MARKED_RE.exec(text);
    if (match) {
      const value = match[1] !== undefined ? amount(match[1], match[2]) : amount(match[3], match[4]);
      if (value >= MIN_BUDGET) {
        high = value;
        spans.push(match[0].trim());
        text = strip(text, match);
      }
    }
  }

  if (low === null && high === null) return { budget: null, remainder: normalized };
  if (low !== null && high !== null && low > high) [low, high] = [high, low];
  return { budget: { min: low, max: high, text: spans.join(" / ") }, remainder: text };
}

const regexCache = new Map();
export function compiled(pattern) {
  let re = regexCache.get(pattern);
  if (!re) {
    re = new RegExp(pattern);
    regexCache.set(pattern, re);
  }
  return re;
}

const wordRe = (phrase) => new RegExp(`(?<![a-z0-9])${escapeRegex(phrase)}(?![a-z0-9])`, "g");

// Pick the product type named last in the query ('laptop bag' -> bag, 'gaming laptop' -> laptop).
// An intent is dropped when the query names one of its accessory terms ('laptop stand').
export function detectIntent(text, intents) {
  let best = null;
  for (const [intentId, spec] of Object.entries(intents)) {
    for (const keyword of spec.query_terms) {
      for (const m of text.matchAll(wordRe(keyword))) {
        const end = m.index + m[0].length;
        if (best === null || end > best.end || (end === best.end && keyword.length > best.len)) {
          best = { end, len: keyword.length, intentId, keyword };
        }
      }
    }
  }
  if (best === null) return null;
  const spec = intents[best.intentId];
  if ((spec.product_exclude || []).some((p) => compiled(p).test(text))) return null;
  return { id: best.intentId, label: spec.label, keyword: best.keyword };
}

// One regex equivalent to patterns.some(p => p.test(...)), but far cheaper to run.
const alternationCache = new WeakMap();
function alternation(patterns) {
  if (!alternationCache.has(patterns)) {
    alternationCache.set(patterns, patterns.length ? new RegExp(patterns.map((p) => `(?:${p})`).join("|")) : null);
  }
  return alternationCache.get(patterns);
}

export function productMatchesIntent(normalizedName, spec) {
  const include = alternation(spec.product_patterns);
  if (!include || !include.test(normalizedName)) return false;
  const exclude = alternation(spec.product_exclude || []);
  return !exclude || !exclude.test(normalizedName);
}

const stopwordCache = new WeakMap();
function stopwordSet(config) {
  if (!stopwordCache.has(config)) stopwordCache.set(config, new Set(config.text.stopwords));
  return stopwordCache.get(config);
}

export function parseQuery(query, config) {
  const textCfg = config.text;
  const trimmed = String(query ?? "").trim();
  const normalized = normalize(trimmed, textCfg.phrase_normalizations);
  const { budget, remainder } = parseBudget(normalized);
  const prefersLowPrice = textCfg.low_price_terms.some((term) => wordRe(term).test(normalized));
  const intent = detectIntent(remainder, config.intents);
  const terms = queryTerms(remainder, stopwordSet(config));
  return {
    query: trimmed,
    normalized,
    search_text: remainder.split(/\s+/).filter(Boolean).join(" "),
    terms,
    budget,
    intent,
    prefers_low_price: prefersLowPrice,
  };
}
