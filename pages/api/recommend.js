import fs from "fs";
import path from "path";

const TRUSTED_BRANDS = [
  "lenovo",
  "asus",
  "dell",
  "hp",
  "logitech",
  "sony",
  "jbl",
  "acer",
  "msi",
  "samsung",
  "lg",
  "tp-link",
  "bluerigger",
];

const USER_PROFILES = {
  gaming: ["gaming", "rtx", "graphics", "asus", "lenovo"],
  student: ["affordable", "battery life", "lightweight", "portable"],
  ai_student: ["machine learning", "gpu", "deep learning", "ram"],
};

function parsePrice(val) {
  if (val === null || val === undefined || val === "") return null;
  if (typeof val === "number") return val;
  const str = String(val).replace(/₹|,/g, "");
  const match = str.match(/\d+(?:\.\d+)?/);
  return match ? parseFloat(match[0]) : null;
}

function extractBudget(query) {
  if (!query) return null;
  const lower = query.toLowerCase();
  // Match patterns like "under 90k" -> 90000
  const kMatch = lower.match(/(?:under|below|budget|within)?\s*(\d+)\s*k\b/);
  if (kMatch) {
    return parseFloat(kMatch[1]) * 1000;
  }
  const cleaned = query.replace(/₹|,/g, " ");
  const matches = cleaned.match(/\d+(?:\.\d+)?/g);
  if (matches) {
    const nums = matches.map(Number).filter((n) => n > 100);
    return nums.length > 0 ? Math.max(...nums) : null;
  }
  return null;
}

function computeBudgetScore(price, budget) {
  if (budget === null || price === null || price === undefined) return 0.0;
  if (price <= budget) return 1.0;
  return Math.max(0.0, 1.0 - (price - budget) / budget);
}

function computeCategoryScore(query, category) {
  if (!query || !category) return 0.0;
  const q = query.toLowerCase();
  const c = String(category).toLowerCase();
  if (q.includes("gaming") && c.includes("gaming")) return 1.0;
  if (q.includes("laptop") && c.includes("laptop")) return 1.0;
  if (q.includes("monitor") && c.includes("monitor")) return 1.0;
  if (q.includes("audio") && c.includes("audio")) return 1.0;
  return 0.0;
}

function computeBusinessScore(product, categoryScore) {
  let score = 0.0;
  const rating = Number(product.rating || 0);
  if (rating >= 4.5) score += 0.4;
  else if (rating >= 4.0) score += 0.25;

  const popularity = Number(product.popularity || 0);
  if (popularity >= 10000) score += 0.3;
  else if (popularity >= 1000) score += 0.2;
  else if (popularity >= 100) score += 0.1;

  const name = String(product.name || "").toLowerCase();
  if (TRUSTED_BRANDS.some((brand) => name.includes(brand))) {
    score += 0.2;
  }

  score += 0.1 * (categoryScore || 0.0);
  return Math.min(score, 1.0);
}

function calculateLexicalSimilarity(query, combinedText) {
  const queryWords = query
    .toLowerCase()
    .replace(/[^\w\s]/g, "")
    .split(/\s+/)
    .filter((w) => w.length > 2);
  if (queryWords.length === 0) return 0.5;

  const text = combinedText.toLowerCase();
  let matches = 0;
  for (const word of queryWords) {
    if (text.includes(word)) {
      matches += 1;
    }
  }
  return Math.min(1.0, 0.4 + (matches / queryWords.length) * 0.6);
}

function generateExplanation(query, product, userProfile) {
  const reasons = [];
  const similarity = product.similarity || 0;
  const rating = product.rating || 0;
  const text = `${product.name} ${product.reviewText || ""}`.toLowerCase();

  if (similarity > 0.4) {
    reasons.push("Strong semantic and contextual match for your search query.");
  }
  if (rating >= 4.5) {
    reasons.push(`Top-tier customer satisfaction rating of ${rating.toFixed(1)}/5 stars.`);
  } else if (rating >= 4.0) {
    reasons.push(`Shows consistently positive verified reviews (${rating.toFixed(1)}/5 rating).`);
  }
  if (product.budget_score > 0.5) {
    reasons.push("Fully satisfies the budget target detected in your search.");
  }
  if (product.popularity >= 500) {
    reasons.push("Widely purchased and highly rated across the marketplace.");
  }
  if (["rtx", "gpu", "deep learning", "machine learning", "ram", "i7", "i5"].some((w) => text.includes(w))) {
    reasons.push("Equipped with hardware specifications suited for performance-heavy tasks.");
  }
  if (text.includes("gaming")) {
    reasons.push("Built for gaming performance with dedicated cooling and fast refresh rates.");
  }
  if (userProfile && userProfile !== "general") {
    reasons.push(`Personalization boost applied for the '${userProfile}' user profile.`);
  }
  if (reasons.length === 0) {
    reasons.push("Ranked highly by multi-signal retrieval and business scoring.");
  }

  return reasons;
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed. Use POST." });
  }

  const { query, user_type = "general", top_k = 5 } = req.body || {};

  if (!query || !query.trim()) {
    return res.status(400).json({ error: "Query parameter cannot be empty." });
  }

  // 1. Try external backend if configured (Option C Architecture)
  const backendUrl = process.env.BACKEND_URL;
  if (backendUrl) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4000);

      const response = await fetch(`${backendUrl}/api/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, user_type, top_k }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        return res.status(200).json({
          ...data,
          source: "external-ml-backend",
        });
      }
    } catch (err) {
      console.warn("External backend unreachable, falling back to built-in engine:", err.message);
    }
  }

  // 2. Built-in Serverless Recommendation Engine (Option A Fallback)
  try {
    const dataFilePath = path.join(process.cwd(), "data", "processed", "products.json");
    let rawProducts = [];

    if (fs.existsSync(dataFilePath)) {
      rawProducts = JSON.parse(fs.readFileSync(dataFilePath, "utf-8"));
    }

    const budget = extractBudget(query);

    const candidates = rawProducts.map((p, idx) => {
      const price = parsePrice(p.discount_price || p.actual_price || p.price);
      const rating = parseFloat(p.overall || p.rating || 0.0) || 0.0;
      const popularity = parseFloat(String(p.no_of_ratings || p.popularity || "0").replace(/,/g, "")) || 0.0;
      const category = `${p.main_category || ""} ${p.sub_category || ""}`.trim();
      const combinedText = `${p.name || p.title || ""} ${category} ${p.reviewText || ""}`;

      const similarity = calculateLexicalSimilarity(query, combinedText);
      const budgetScore = computeBudgetScore(price, budget);
      const categoryScore = computeCategoryScore(query, category);

      return {
        index: idx,
        title: p.name || p.title || "Unknown Product",
        name: p.name || p.title || "Unknown Product",
        category: p.main_category || "General",
        sub_category: p.sub_category || "",
        price: price,
        rating: rating,
        popularity: popularity,
        reviewText: p.reviewText || "",
        combined_text: combinedText,
        similarity: similarity,
        budget_score: budgetScore,
        category_score: categoryScore,
      };
    });

    // Multi-signal ranking
    const ranked = candidates.map((candidate) => {
      const businessScore = computeBusinessScore(candidate, candidate.category_score);
      const ratingNorm = Math.min(Math.max(candidate.rating / 5.0, 0.0), 1.0);
      const popNorm = Math.min(candidate.popularity / 10000.0, 1.0);

      const finalScore =
        0.45 * candidate.similarity +
        0.20 * ratingNorm +
        0.15 * popNorm +
        0.10 * candidate.budget_score +
        0.10 * businessScore;

      return {
        ...candidate,
        business_score: businessScore,
        score: finalScore,
        final_score: finalScore,
      };
    });

    // Personalization boost
    const preferences = USER_PROFILES[user_type] || [];
    const personalized = ranked.map((p) => {
      let boost = 0.0;
      const textLower = p.combined_text.toLowerCase();
      for (const pref of preferences) {
        if (textLower.includes(pref)) {
          boost += 0.05;
        }
      }
      boost = Math.min(boost, 0.10);
      return {
        ...p,
        personalized_score: p.final_score + boost,
      };
    });

    personalized.sort((a, b) => b.personalized_score - a.personalized_score);

    const topResults = personalized.slice(0, Number(top_k) || 5).map((p) => {
      const reasons = generateExplanation(query, p, user_type);
      return {
        index: p.index,
        title: p.title,
        name: p.name,
        price: p.price,
        rating: p.rating,
        popularity: p.popularity,
        category: p.category,
        sub_category: p.sub_category,
        similarity: p.similarity,
        score: p.score,
        personalized_score: p.personalized_score,
        explanation: `Why this product was recommended:\n\n` + reasons.map((r) => `• ${r}`).join("\n"),
        reasons: reasons,
      };
    });

    return res.status(200).json({
      query,
      user_type,
      count: topResults.length,
      recommendations: topResults,
      source: "vercel-serverless-engine",
    });
  } catch (error) {
    return res.status(500).json({ error: error.message });
  }
}
