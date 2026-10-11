// API route handlers exercised with mock req/res objects against the real catalog.

import assert from "node:assert/strict";
import http from "node:http";
import { after, before, test } from "node:test";

import catalogHandler from "../../pages/api/catalog.js";
import healthHandler from "../../pages/api/health.js";
import recommendHandler from "../../pages/api/recommend.js";
import similarHandler from "../../pages/api/similar.js";

function mockRes() {
  const res = {
    statusCode: 200,
    headers: {},
    body: undefined,
    setHeader(name, value) {
      this.headers[name.toLowerCase()] = value;
    },
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(body) {
      this.body = body;
      return this;
    },
  };
  return res;
}

async function call(handler, req) {
  const res = mockRes();
  await handler({ query: {}, headers: {}, ...req }, res);
  return res;
}

const withBackend = async (url, fn) => {
  const previous = process.env.BACKEND_URL;
  process.env.BACKEND_URL = url;
  try {
    return await fn();
  } finally {
    if (previous === undefined) delete process.env.BACKEND_URL;
    else process.env.BACKEND_URL = previous;
  }
};

// A stand-in for the Python backend with a configurable reply.
let backend;
let backendReply = { status: 200, body: {} };
before(async () => {
  backend = http.createServer((req, res) => {
    res.writeHead(backendReply.status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(backendReply.body));
  });
  await new Promise((resolve) => backend.listen(0, "127.0.0.1", resolve));
});
after(() => backend.close());
const backendAddress = () => `http://127.0.0.1:${backend.address().port}`;

test("recommend rejects non-POST and invalid bodies", async () => {
  assert.equal((await call(recommendHandler, { method: "GET" })).statusCode, 405);
  for (const body of [
    {},
    { query: "   " },
    { query: "x".repeat(201) },
    { query: "laptop", profile: "pirate" },
    { query: "laptop", top_k: 0 },
    { query: "laptop", top_k: 500 },
    { query: "laptop", filters: { department: "Nope" } },
    { query: "laptop", filters: { min_price: 500, max_price: 100 } },
    { query: "laptop", filters: { min_rating: 9 } },
  ]) {
    const res = await call(recommendHandler, { method: "POST", body });
    assert.equal(res.statusCode, 400, JSON.stringify(body));
    assert.ok(res.body.error);
  }
});

test("recommend without a backend serves the keyword engine and says so", async () => {
  const res = await withBackend("", () =>
    call(recommendHandler, { method: "POST", body: { query: "wireless earbuds under 2000", top_k: 5 } }),
  );
  assert.equal(res.statusCode, 200);
  assert.equal(res.body.served_by, "next-lexical");
  assert.equal(res.body.engine.mode, "lexical");
  assert.equal(res.body.engine.degraded, false);
  assert.match(res.body.engine.notice, /no semantic backend/);
  assert.equal(res.body.results.length, 5);
  assert.ok(res.body.results.every((r) => r.price <= 2000));
});

test("recommend proxies to a healthy backend", async () => {
  backendReply = { status: 200, body: { query: "x", results: [], engine: { mode: "hybrid" } } };
  const res = await withBackend(backendAddress(), () =>
    call(recommendHandler, { method: "POST", body: { query: "earbuds" } }),
  );
  assert.equal(res.body.served_by, "python-backend");
  assert.equal(res.body.engine.mode, "hybrid");
});

test("recommend falls back when the backend errors or is unreachable", async () => {
  backendReply = { status: 503, body: { error: "loading" } };
  let res = await withBackend(backendAddress(), () => call(recommendHandler, { method: "POST", body: { query: "earbuds" } }));
  assert.equal(res.body.served_by, "next-lexical");
  assert.equal(res.body.engine.degraded, true);
  assert.match(res.body.engine.notice, /starting up/);

  res = await withBackend("http://127.0.0.1:9", () => call(recommendHandler, { method: "POST", body: { query: "earbuds" } }));
  assert.equal(res.body.served_by, "next-lexical");
  assert.match(res.body.engine.notice, /unreachable/);
});

test("recommend relays backend validation errors instead of masking them", async () => {
  backendReply = { status: 400, body: { error: "query: too long" } };
  const res = await withBackend(backendAddress(), () => call(recommendHandler, { method: "POST", body: { query: "earbuds" } }));
  assert.equal(res.statusCode, 400);
  assert.equal(res.body.error, "query: too long");
});

test("similar validates input and finds neighbours", async () => {
  assert.equal((await call(similarHandler, { method: "GET", query: { asin: "bad" } })).statusCode, 400);
  assert.equal((await call(similarHandler, { method: "GET", query: { asin: "B000000000" } })).statusCode, 404);
  const rec = await withBackend("", () => call(recommendHandler, { method: "POST", body: { query: "bluetooth speaker", top_k: 1 } }));
  const asin = rec.body.results[0].asin;
  const res = await withBackend("", () => call(similarHandler, { method: "GET", query: { asin, k: "4" } }));
  assert.equal(res.statusCode, 200);
  assert.equal(res.body.results.length, 4);
  assert.ok(res.body.results.every((r) => r.asin !== asin));
});

test("catalog and health endpoints", async () => {
  const catalog = await call(catalogHandler, { method: "GET" });
  assert.equal(catalog.statusCode, 200);
  assert.ok(catalog.body.total_products > 1000);
  assert.ok(catalog.body.departments.length > 5);
  assert.deepEqual(Object.keys(catalog.body.profiles).sort(), ["ai_student", "gaming", "general", "student"]);

  const health = await withBackend("", () => call(healthHandler, { method: "GET" }));
  assert.equal(health.body.status, "ok");
  assert.equal(health.body.mode, "lexical");
  assert.equal(health.body.backend.configured, false);
  assert.ok(!JSON.stringify(health.body).includes("127.0.0.1"));
});
