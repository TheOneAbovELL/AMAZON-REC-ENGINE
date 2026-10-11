import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { LexicalEngine, UnknownProductError } from "../../lib/engine/engine.mjs";
import { formatInr } from "../../lib/engine/explainer.mjs";
import { parseQuery } from "../../lib/engine/queryParser.mjs";
import { normalize, stem, tokenize, variantKey } from "../../lib/engine/text.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const readJson = (rel) => JSON.parse(fs.readFileSync(path.join(root, rel), "utf-8"));
const config = readJson("config/engine.json");
const engine = new LexicalEngine(readJson("tests/fixtures/mini_catalog.json"), config);
const asins = (response) => response.results.map((r) => r.asin);

test("query fixture cases (shared with the Python suite)", () => {
  for (const c of readJson("tests/fixtures/query_cases.json")) {
    const parsed = parseQuery(c.query, config);
    const budget = parsed.budget ? { min: parsed.budget.min, max: parsed.budget.max } : null;
    assert.deepEqual(budget, c.budget, c.query);
    assert.equal(parsed.intent?.id ?? null, c.intent, c.query);
    assert.deepEqual(parsed.terms, c.terms, c.query);
    assert.equal(parsed.prefers_low_price, c.prefers_low_price, c.query);
  }
});

test("text fixture cases (shared with the Python suite)", () => {
  const phraseMap = config.text.phrase_normalizations;
  for (const c of readJson("tests/fixtures/text_cases.json")) {
    assert.deepEqual(tokenize(c.text, phraseMap), c.tokens, c.text);
    assert.equal(variantKey(normalize(c.text, phraseMap), 3), c.variant_key, c.text);
  }
});

test("stemming and rupee formatting", () => {
  assert.equal(stem("earbuds"), "earbud");
  assert.equal(stem("batteries"), "battery");
  assert.equal(stem("tennis"), "tennis");
  assert.equal(formatInr(125000), "₹1,25,000");
  assert.equal(formatInr(999.5), "₹1,000");
  assert.equal(formatInr(450), "₹450");
});

test("budget is a hard filter", () => {
  const response = engine.recommend("gaming laptop under 80k", { topK: 10 });
  assert.ok(response.results.length > 0);
  assert.ok(response.results.every((r) => r.price <= 80000));
  assert.equal(response.filters.max_price, 80000);
});

test("product type outranks accessories, accessory queries return accessories", () => {
  const laptops = engine.recommend("laptop", { topK: 5 });
  assert.ok(laptops.results.slice(0, 3).every((r) => r.intent_match));
  assert.equal(engine.recommend("laptop bag", { topK: 3 }).results[0].asin, "TLBAG00001");
});

test("variants that share a review pool are collapsed", () => {
  const galaxy = asins(engine.recommend("samsung galaxy m13", { topK: 5 })).filter((a) => a.startsWith("TPHONE000") && a <= "TPHONE0002");
  assert.equal(galaxy.length, 1);
});

test("profiles change the ranking and are explained", () => {
  const general = engine.recommend("laptop", { profile: "general", topK: 5 });
  const gamer = engine.recommend("laptop", { profile: "gaming", topK: 5 });
  assert.notDeepEqual(asins(general), asins(gamer));
  assert.ok(gamer.results[0].reasons.some((r) => r.includes("Gamer profile")));
});

test("unknown profile is rejected and empty intent asks for more", () => {
  assert.throws(() => engine.recommend("laptop", { profile: "pirate" }), /Unknown profile/);
  const response = engine.recommend("under 5000");
  assert.deepEqual(response.results, []);
  assert.ok(response.message);
});

test("scores are sorted and contributions add up", () => {
  const response = engine.recommend("noise cancelling earbuds", { topK: 5 });
  const scores = response.results.map((r) => r.score);
  assert.deepEqual(scores, [...scores].sort((a, b) => b - a));
  for (const r of response.results) {
    const sum = Object.values(r.contributions).reduce((a, b) => a + b, 0);
    assert.ok(Math.abs(sum - r.score) < 1e-5);
  }
});

test("similar items exclude the product and its variants", () => {
  const response = engine.similar("TPHONE0001", 5);
  assert.ok(!asins(response).includes("TPHONE0001"));
  assert.ok(!asins(response).includes("TPHONE0002"));
  assert.throws(() => engine.similar("B000000000"), UnknownProductError);
});
