// Request validation shared by the Next.js API routes. Limits match api_server.py.

export const LIMITS = {
  queryMaxLength: 200,
  topKMax: 50,
  topKDefault: 12,
  similarMax: 24,
  similarDefault: 8,
  priceMax: 10_000_000,
};

export class ValidationError extends Error {}

function optionalNumber(value, name, { min, max }) {
  if (value === undefined || value === null || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n) || n < min || n > max) throw new ValidationError(`${name} must be a number between ${min} and ${max}.`);
  return n;
}

function boundedInt(value, name, { min, max, fallback }) {
  if (value === undefined || value === null || value === "") return fallback;
  const n = Number(value);
  if (!Number.isInteger(n) || n < min || n > max) throw new ValidationError(`${name} must be an integer between ${min} and ${max}.`);
  return n;
}

export function validateRecommendRequest(body, { profiles, departments }) {
  if (!body || typeof body !== "object" || Array.isArray(body)) throw new ValidationError("Request body must be a JSON object.");
  const query = typeof body.query === "string" ? body.query.trim() : "";
  if (!query) throw new ValidationError("query is required.");
  if (query.length > LIMITS.queryMaxLength) throw new ValidationError(`query must be at most ${LIMITS.queryMaxLength} characters.`);

  const profile = body.profile ?? "general";
  if (typeof profile !== "string" || !profiles.includes(profile)) {
    throw new ValidationError(`profile must be one of: ${profiles.join(", ")}.`);
  }
  const topK = boundedInt(body.top_k, "top_k", { min: 1, max: LIMITS.topKMax, fallback: LIMITS.topKDefault });

  const raw = body.filters ?? {};
  if (typeof raw !== "object" || Array.isArray(raw)) throw new ValidationError("filters must be an object.");
  let department = raw.department ?? null;
  if (department === "") department = null;
  if (department !== null && (typeof department !== "string" || !departments.includes(department))) {
    throw new ValidationError("filters.department is not a known department.");
  }
  const filters = {
    department,
    min_price: optionalNumber(raw.min_price, "filters.min_price", { min: 0, max: LIMITS.priceMax }),
    max_price: optionalNumber(raw.max_price, "filters.max_price", { min: 0, max: LIMITS.priceMax }),
    min_rating: optionalNumber(raw.min_rating, "filters.min_rating", { min: 0, max: 5 }),
  };
  if (filters.min_price !== null && filters.max_price !== null && filters.min_price > filters.max_price) {
    throw new ValidationError("filters.min_price cannot exceed filters.max_price.");
  }
  return { query, profile, top_k: topK, filters };
}

const ASIN_RE = /^[A-Z0-9]{10}$/;

export function validateSimilarRequest(query) {
  const asin = typeof query.asin === "string" ? query.asin.trim().toUpperCase() : "";
  if (!ASIN_RE.test(asin)) throw new ValidationError("asin must be a 10-character Amazon product id.");
  const k = boundedInt(query.k, "k", { min: 1, max: LIMITS.similarMax, fallback: LIMITS.similarDefault });
  return { asin, k };
}
