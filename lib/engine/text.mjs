// Text normalisation and tokenisation. Mirrors src/text.py exactly;
// tests/fixtures/text_cases.json is asserted by both test suites.

const TOKEN_RE = /[a-z0-9]+/g;
// "16 GB" -> "16gb", "43 inches" / 43" -> "43inch" so specs match however they are written.
const UNIT_RE = /(\d)\s*(inches|inch|gb|tb|hz|mah|mp|w|kg|ml)\b|(\d)\s*("|”)/g;
const UNIT_CANON = { inches: "inch", '"': "inch", "”": "inch" };

export const escapeRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const phraseCache = new WeakMap();
function phrasePattern(phraseMap) {
  if (!phraseCache.has(phraseMap)) {
    const phrases = Object.keys(phraseMap).sort((a, b) => b.length - a.length);
    phraseCache.set(
      phraseMap,
      phrases.length ? new RegExp(`(?<![a-z0-9])(${phrases.map(escapeRegex).join("|")})(?![a-z0-9])`, "g") : null,
    );
  }
  return phraseCache.get(phraseMap);
}

export function normalize(text, phraseMap) {
  let lowered = String(text ?? "").toLowerCase();
  const pattern = phrasePattern(phraseMap);
  if (pattern) lowered = lowered.replace(pattern, (m) => phraseMap[m]);
  return lowered.replace(UNIT_RE, (m, d1, u1, d2, u2) => (d1 !== undefined ? d1 + (UNIT_CANON[u1] ?? u1) : d2 + UNIT_CANON[u2]));
}

export function stem(token) {
  if (/\d/.test(token)) return token;
  if (token.length > 4 && token.endsWith("ies")) return token.slice(0, -3) + "y";
  if (
    token.length > 4 &&
    (token.endsWith("ches") || token.endsWith("shes") || (token.endsWith("es") && "sxz".includes(token[token.length - 3])))
  ) {
    return token.slice(0, -2);
  }
  if (token.length > 3 && token.endsWith("s") && !token.endsWith("ss") && !token.endsWith("us") && !token.endsWith("is")) {
    return token.slice(0, -1);
  }
  return token;
}

export function rawTokens(normalized) {
  return (normalized.match(TOKEN_RE) || []).filter((t) => t.length > 1 || /^\d+$/.test(t));
}

export function tokenize(text, phraseMap) {
  return rawTokens(normalize(text, phraseMap)).map(stem);
}

export function queryTerms(normalizedQuery, stopwords) {
  const seen = new Set();
  for (const token of rawTokens(normalizedQuery)) {
    if (stopwords.has(token)) continue;
    seen.add(stem(token));
  }
  return [...seen];
}

const BRACKETS_RE = /\([^)]*\)|\[[^\]]*\]/g;

// Leading title words outside brackets: '(Aqua Green, 4GB)' variants share a key.
export function variantKey(normalizedName, tokens) {
  return rawTokens(normalizedName.replace(BRACKETS_RE, " ")).slice(0, tokens).join(" ");
}
