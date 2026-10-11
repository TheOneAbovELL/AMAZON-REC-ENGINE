export { formatInr } from "./engine/explainer.mjs";

export function formatCount(n) {
  if (n >= 100000) return `${(n / 100000).toFixed(n >= 1000000 ? 0 : 1)}L`;
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`;
  return String(n);
}

export const SIGNAL_LABELS = {
  relevance: "Relevance",
  quality: "Rating quality",
  popularity: "Popularity",
  deal: "Discount",
  profile: "Profile fit",
};
