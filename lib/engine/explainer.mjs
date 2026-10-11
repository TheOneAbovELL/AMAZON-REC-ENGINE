// Human-readable reasons derived only from measured ranking signals. Mirrors src/explainer.py.

export function formatInr(value) {
  const whole = Math.round(value);
  let digits = String(Math.abs(whole));
  if (digits.length > 3) {
    let head = digits.slice(0, -3);
    const tail = digits.slice(-3);
    const groups = [];
    while (head.length > 2) {
      groups.unshift(head.slice(-2));
      head = head.slice(0, -2);
    }
    if (head) groups.unshift(head);
    digits = groups.join(",") + "," + tail;
  }
  return (whole < 0 ? "-" : "") + "₹" + digits;
}

export function explain(item, { matchedTerms, semantic, cosine = null, intent, intentMatch, budget, profileId, profile, profileHits, cheap }) {
  const reasons = [];
  if (intent && intentMatch) reasons.push(`Matches what you asked for: ${intent.label.toLowerCase()}.`);
  if (matchedTerms.length) {
    reasons.push(`Listing mentions ${matchedTerms.slice(0, 4).map((t) => `“${t}”`).join(", ")}.`);
  }
  if (semantic !== null && semantic !== undefined && semantic >= 0.5 && cosine !== null) {
    reasons.push(`Close in meaning to your query (cosine similarity ${cosine.toFixed(2)}).`);
  }
  if (budget) {
    const price = item.price;
    if (budget.max !== null && budget.min !== null) {
      reasons.push(`${formatInr(price)} is inside your ${formatInr(budget.min)}–${formatInr(budget.max)} range.`);
    } else if (budget.max !== null) {
      reasons.push(`${formatInr(price)} fits your ${formatInr(budget.max)} budget.`);
    } else if (budget.min !== null) {
      reasons.push(`${formatInr(price)} is above your ${formatInr(budget.min)} minimum.`);
    }
  }
  if (item.rating_count >= 50 && item.rating >= 4.0) {
    reasons.push(`Rated ${item.rating.toFixed(1)}★ across ${item.rating_count.toLocaleString("en-US")} ratings.`);
  } else if (item.rating_count < 50) {
    reasons.push(`Only ${item.rating_count} ratings so far, so its ${item.rating.toFixed(1)}★ is less certain.`);
  }
  if (item.discount_pct >= 20) reasons.push(`${item.discount_pct}% below its list price.`);
  if (profileId !== "general" && profileHits.length) {
    reasons.push(`Fits your ${profile.label} profile: ${profileHits.slice(0, 4).join(", ")}.`);
  }
  if (cheap !== null && cheap !== undefined && cheap >= 0.6) reasons.push("Cheaper than most of the relevant options.");
  return reasons;
}
