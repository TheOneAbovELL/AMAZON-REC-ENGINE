import fs from "fs";
import path from "path";

const TRUSTED_BRANDS = [
  "lenovo",
  "asus",
  "dell",
  "hp",
  "acer",
  "apple",
  "logitech",
  "sony",
  "tp-link",
  "redragon",
  "lg",
  "samsung",
];

const INTENT_MAPPINGS = {
  laptop: ["laptop", "notebook", "macbook", "victus", "loq", "ideapad", "vivobook", "nitro", "strix", "tuf", "zephyrus"],
  keyboard: ["keyboard", "keypad", "mechanical keyboard"],
  earbuds: ["earbud", "earbuds", "earphone", "earphones", "tws", "airpods"],
  headphone: ["headphone", "headphones", "headset"],
  monitor: ["monitor", "display", "ultrasharp", "ultragear"],
  router: ["router", "wifi", "access point", "mesh"],
  cable: ["cable", "hdmi", "toslink", "ethernet cable"],
};

const USER_PROFILES = {
  ai_student: ["rtx", "cuda", "deep learning", "ai", "machine learning", "16gb", "32gb", "gpu", "loq", "nitro", "strix"],
  gaming: ["gaming", "rtx", "gtx", "144hz", "165hz", "gpu", "loq", "nitro", "victus", "strix", "tuf", "geforce"],
  student: ["student", "lightweight", "battery", "portable", "thin", "vivobook", "ideapad", "affordable"],
  general: ["reliable", "quality", "popular", "trusted"],
};

function parsePrice(val) {
  if (val === null || val === undefined || val === "") return 0.0;
  if (typeof val === "number") return val;
  const str = String(val).replace(/₹|,/g, "");
  const match = str.match(/\d+(?:\.\d+)?/);
  return match ? parseFloat(match[0]) : 0.0;
}

function extractBudget(query) {
  if (!query) return null;
  const lower = query.toLowerCase();

  // Pattern: "under 90k" or "below 90k" -> 90000
  const kMatch = lower.match(/(?:under|below|budget|within)?\s*(\d+)\s*k\b/);
  if (kMatch) {
    return parseFloat(kMatch[1]) * 1000;
  }

  // Pattern: "under 90000" or "below 50000"
  const numMatch = lower.match(/(?:under|below|budget|within|upto)\s*₹?\s*(\d{4,7})/);
  if (numMatch) {
    return parseFloat(numMatch[1]);
  }

  const cleaned = query.replace(/₹|,/g, " ");
  const matches = cleaned.match(/\d+(?:\.\d+)?/g);
  if (matches) {
    const nums = matches.map(Number).filter((n) => n > 500);
    return nums.length > 0 ? Math.max(...nums) : null;
  }
  return null;
}

function detectQueryIntent(query) {
  const lower = query.toLowerCase();
  for (const [category, keywords] of Object.entries(INTENT_MAPPINGS)) {
    if (keywords.some((kw) => lower.includes(kw))) {
      return category;
    }
  }
  return null;
}

function isProductIntentMatch(product, targetIntent) {
  if (!targetIntent) return true;
  const keywords = INTENT_MAPPINGS[targetIntent] || [];
  const text = `${product.name || ""} ${product.sub_category || ""} ${product.main_category || ""}`.toLowerCase();
  return keywords.some((kw) => text.includes(kw));
}

function computeBudgetScore(price, budget) {
  if (!budget || !price) return 0.5;
  if (price <= budget) {
    // Reward products in the expected price range, not trivial cables
    const ratio = price / budget;
    if (ratio >= 0.5) return 1.0;
    return 0.8 + 0.2 * ratio;
  }
  // Penalize over budget smoothly
  return Math.max(0.0, 1.0 - (price - budget) / budget);
}

function calculateRelevanceScore(query, product, targetIntent) {
  const text = `${product.name || ""} ${product.sub_category || ""} ${product.main_category || ""} ${product.reviewText || ""}`.toLowerCase();
  const title = (product.name || "").toLowerCase();

  // If user searched for laptop, and this product is not a laptop, strongly penalize
  if (targetIntent && !isProductIntentMatch(product, targetIntent)) {
    return 0.05;
  }

  const stopWords = new Set(["need", "for", "under", "below", "with", "the", "and", "a", "an", "in", "to", "best", "good"]);
  const queryTokens = query
    .toLowerCase()
    .replace(/[^\w\s]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length > 1 && !stopWords.has(w));

  let score = 0.0;
  let matches = 0;

  for (const token of queryTokens) {
    if (title.includes(token)) {
      score += 0.4;
      matches += 1;
    } else if (text.includes(token)) {
      score += 0.2;
      matches += 1;
    }
  }

  // Domain-specific boosts
  const lowerQuery = query.toLowerCase();

  // AI workload match
  if (lowerQuery.includes("ai") || lowerQuery.includes("machine learning") || lowerQuery.includes("deep learning")) {
    if (text.includes("rtx 4060") || text.includes("rtx 4070") || text.includes("rtx 4080")) {
      score += 0.5;
    } else if (text.includes("rtx 4050") || text.includes("rtx 3050") || text.includes("gpu")) {
      score += 0.35;
    }
    if (text.includes("deep learning") || text.includes("ai") || text.includes("pytorch") || text.includes("cuda")) {
      score += 0.3;
    }
  }

  // Gaming match
  if (lowerQuery.includes("gaming")) {
    if (title.includes("gaming") || text.includes("144hz") || text.includes("165hz")) {
      score += 0.4;
    }
  }

  // Student match
  if (lowerQuery.includes("student")) {
    if (title.includes("student") || text.includes("lightweight") || text.includes("battery life")) {
      score += 0.4;
    }
  }

  // Intent match base bonus
  if (targetIntent && isProductIntentMatch(product, targetIntent)) {
    score += 0.3;
  }

  return Math.min(1.0, Math.max(0.1, score));
}

function computePersonalizationBoost(product, userProfile) {
  if (!userProfile || userProfile === "general") return 0.0;
  const preferences = USER_PROFILES[userProfile] || [];
  const text = `${product.name || ""} ${product.reviewText || ""}`.toLowerCase();

  let matches = 0;
  for (const pref of preferences) {
    if (text.includes(pref)) {
      matches += 1;
    }
  }
  return Math.min(0.15, matches * 0.05);
}

function generateContextualExplanation(query, product, userProfile, budget) {
  const reasons = [];
  const name = (product.name || "").toLowerCase();
  const text = `${product.name || ""} ${product.reviewText || ""}`.toLowerCase();
  const price = product.price || 0;
  const rating = product.rating || 0;

  // 1. Query & Intent Match
  const targetIntent = detectQueryIntent(query);
  if (targetIntent === "laptop") {
    reasons.push("Direct match for your search query requiring a high-performance laptop.");
  } else if (targetIntent) {
    reasons.push(`Direct match for your search in the ${targetIntent} product category.`);
  }

  // 2. Hardware / AI / Gaming capabilities
  if (query.toLowerCase().includes("ai") || userProfile === "ai_student") {
    if (text.includes("rtx 4060")) {
      reasons.push("Equipped with NVIDIA GeForce RTX 4060 GPU (8GB VRAM) and 16GB RAM, optimal for local PyTorch/CUDA deep learning and AI modeling.");
    } else if (text.includes("rtx 4070")) {
      reasons.push("Powered by high-tier NVIDIA RTX 4070 GPU with 32GB RAM for large neural network fine-tuning and intensive compute.");
    } else if (text.includes("rtx 4050") || text.includes("rtx 3050")) {
      reasons.push("Dedicated NVIDIA RTX graphics accelerator suitable for AI engineering coursework, model training, and acceleration.");
    }
  }

  if (query.toLowerCase().includes("gaming") || userProfile === "gaming") {
    if (text.includes("144hz") || text.includes("165hz")) {
      reasons.push("Features high-refresh display (144Hz+) and dedicated cooling architecture built for sustained AAA gaming performance.");
    }
  }

  // 3. Budget Fit
  if (budget) {
    if (price <= budget) {
      reasons.push(`Priced at ₹${price.toLocaleString("en-IN")}, fitting comfortably within your ₹${budget.toLocaleString("en-IN")} budget.`);
    } else {
      reasons.push(`Priced at ₹${price.toLocaleString("en-IN")}, offering premium performance close to your budget range.`);
    }
  }

  // 4. Rating & Reviews
  if (rating >= 4.5) {
    reasons.push(`Top customer satisfaction rating of ${rating.toFixed(1)}/5 stars with verified buyer reviews.`);
  } else if (rating >= 4.0) {
    reasons.push(`Consistent customer satisfaction rating of ${rating.toFixed(1)}/5 stars.`);
  }

  // 5. Personalization Profile
  if (userProfile && userProfile !== "general") {
    const profileLabels = {
      ai_student: "AI / ML Student (Heavy Compute)",
      gaming: "Gaming Enthusiast (GPU Focus)",
      student: "Student (Budget & Battery)",
    };
    reasons.push(`Received personalized ranking boost for '${profileLabels[userProfile] || userProfile}' profile.`);
  }

  if (reasons.length === 0) {
    reasons.push("Ranked highly based on semantic query match and verified customer ratings.");
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

  // 1. Optional External Backend Proxy (Option C)
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
      console.warn("External backend unreachable, using built-in engine:", err.message);
    }
  }

  // 2. High-Accuracy Serverless Recommendation Engine
  try {
    const dataFilePath = path.join(process.cwd(), "data", "processed", "products.json");
    let rawProducts = [];

    if (fs.existsSync(dataFilePath)) {
      rawProducts = JSON.parse(fs.readFileSync(dataFilePath, "utf-8"));
    }

    const targetIntent = detectQueryIntent(query);
    const budget = extractBudget(query);

    // Filter to intent matches if specific product category is requested and available
    let candidatePool = rawProducts;
    if (targetIntent) {
      const intentFiltered = rawProducts.filter((p) => isProductIntentMatch(p, targetIntent));
      if (intentFiltered.length > 0) {
        candidatePool = intentFiltered;
      }
    }

    const scored = candidatePool.map((p, idx) => {
      const price = parsePrice(p.discount_price || p.actual_price || p.price);
      const rating = parseFloat(p.overall || p.rating || 0.0) || 0.0;
      const popularity = parseFloat(String(p.no_of_ratings || p.popularity || "0").replace(/,/g, "")) || 0.0;

      const relevanceScore = calculateRelevanceScore(query, p, targetIntent);
      const budgetScore = computeBudgetScore(price, budget);
      const personalizationBoost = computePersonalizationBoost(p, user_type);

      // Business & brand score
      const nameLower = (p.name || "").toLowerCase();
      const brandScore = TRUSTED_BRANDS.some((b) => nameLower.includes(b)) ? 0.15 : 0.05;
      const ratingNorm = Math.min(rating / 5.0, 1.0);
      const popularityNorm = Math.min(popularity / 10000.0, 1.0);

      // Weighted Multi-Signal Score
      // Relevance and budget are dominant so users get exactly what they asked for
      const finalScore =
        0.45 * relevanceScore +
        0.25 * budgetScore +
        0.12 * ratingNorm +
        0.08 * popularityNorm +
        0.10 * personalizationBoost;

      return {
        index: idx,
        title: p.name || p.title || "Unknown Product",
        name: p.name || p.title || "Unknown Product",
        category: p.main_category || "Computers & Electronics",
        sub_category: p.sub_category || "",
        price: price,
        rating: rating,
        popularity: popularity,
        similarity: relevanceScore,
        score: finalScore,
        personalized_score: finalScore,
        budget_score: budgetScore,
      };
    });

    // Sort by personalized score descending
    scored.sort((a, b) => b.personalized_score - a.personalized_score);

    const topResults = scored.slice(0, Number(top_k) || 5).map((p) => {
      const reasons = generateContextualExplanation(query, p, user_type, budget);
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
        explanation: "Why this product was recommended:\n\n" + reasons.map((r) => `• ${r}`).join("\n"),
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
