import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useCallback, useEffect, useRef, useState } from "react";

import CatalogInsights from "../components/CatalogInsights";
import ResultCard from "../components/ResultCard";
import SimilarDrawer from "../components/SimilarDrawer";
import { formatInr } from "../lib/format.mjs";
import styles from "../styles/app.module.css";

const DEFAULT_QUERY = "laptop for AI under 90k";
const DEFAULT_PROFILE = "ai_student";
const SAMPLE_QUERIES = [
  "laptop for AI under 90k",
  "wireless earbuds under 2000",
  "43 inch smart tv",
  "noise cancelling headphones",
  "running shoes for men",
  "gaming mouse",
  "cotton kurti under 800",
  "pressure cooker 5 litre",
];
const PROFILE_ORDER = ["general", "student", "ai_student", "gaming"];
const RATING_OPTIONS = [
  ["", "Any rating"],
  ["3.5", "3.5★ & up"],
  ["4", "4★ & up"],
  ["4.5", "4.5★ & up"],
];

const toNumberOrNull = (v) => (v === "" || v === undefined || v === null || Number.isNaN(Number(v)) ? null : Number(v));

function EngineBadge({ health }) {
  if (!health) return <span className={styles.badge}>Checking engine…</span>;
  const hybrid = health.mode === "hybrid";
  return (
    <span className={`${styles.badge} ${hybrid ? styles.badgeGood : ""}`} title={hybrid ? health.backend?.model || "" : ""}>
      <span className={styles.dot} aria-hidden="true" />
      {hybrid ? "Semantic + keyword engine" : "Keyword engine"}
    </span>
  );
}

function Interpretation({ data, profiles }) {
  const { interpretation: it, filters } = data;
  const chips = [];
  if (it.intent) chips.push(["Looking for", it.intent.label]);
  if (filters.max_price != null || filters.min_price != null) {
    const lo = filters.min_price != null ? formatInr(filters.min_price) : null;
    const hi = filters.max_price != null ? formatInr(filters.max_price) : null;
    chips.push(["Price", lo && hi ? `${lo} – ${hi}` : hi ? `up to ${hi}` : `from ${lo}`]);
  }
  if (filters.department) chips.push(["Department", filters.department]);
  if (filters.min_rating != null) chips.push(["Rating", `${filters.min_rating}★ & up`]);
  if (it.terms.length) chips.push(["Keywords", it.terms.join(", ")]);
  if (it.prefers_low_price) chips.push(["Preference", "lower prices"]);
  chips.push(["Profile", profiles?.[data.profile]?.label || data.profile]);
  return (
    <ul className={styles.chips} aria-label="How your search was interpreted">
      {chips.map(([k, v]) => (
        <li key={k} className={styles.chip}>
          <span className={styles.chipKey}>{k}</span> {v}
        </li>
      ))}
    </ul>
  );
}

function SkeletonList() {
  return (
    <ol className={styles.results} aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <li key={i} className={`${styles.card} ${styles.skeleton}`}>
          <div className={styles.skeletonBlock} style={{ width: 132, height: 132 }} />
          <div className={styles.cardBody}>
            <div className={styles.skeletonBlock} style={{ width: "40%", height: 12 }} />
            <div className={styles.skeletonBlock} style={{ width: "90%", height: 18, marginTop: 10 }} />
            <div className={styles.skeletonBlock} style={{ width: "60%", height: 14, marginTop: 10 }} />
          </div>
        </li>
      ))}
    </ol>
  );
}

export default function Home() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [profile, setProfile] = useState(DEFAULT_PROFILE);
  const [department, setDepartment] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [minRating, setMinRating] = useState("");
  const [result, setResult] = useState({ status: "idle", data: null, error: null });
  const [catalog, setCatalog] = useState(null);
  const [health, setHealth] = useState(null);
  const [similarFor, setSimilarFor] = useState(null);
  const inflight = useRef(null);
  const similarTrigger = useRef(null);
  const openSimilar = useCallback((item, trigger) => {
    similarTrigger.current = trigger ?? null;
    setSimilarFor(item);
  }, []);
  const closeSimilar = useCallback(() => {
    setSimilarFor(null);
    // Return focus to the button that opened the drawer (Safari does not focus buttons on click).
    similarTrigger.current?.focus();
  }, []);
  const started = useRef(false);

  const search = useCallback(
    async (params) => {
      const q = params.query.trim();
      if (!q) return;
      inflight.current?.abort();
      const controller = new AbortController();
      inflight.current = controller;
      setResult((prev) => ({ status: "loading", data: prev.data, error: null }));

      const urlQuery = { q, profile: params.profile };
      if (params.department) urlQuery.dept = params.department;
      if (params.maxPrice) urlQuery.max = params.maxPrice;
      if (params.minRating) urlQuery.rating = params.minRating;
      router.replace({ pathname: "/", query: urlQuery }, undefined, { shallow: true, scroll: false });

      try {
        const res = await fetch("/api/recommend", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            query: q,
            profile: params.profile,
            top_k: 12,
            filters: {
              department: params.department || null,
              max_price: toNumberOrNull(params.maxPrice),
              min_rating: toNumberOrNull(params.minRating),
            },
          }),
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.error || `Request failed (${res.status}).`);
        setResult({ status: "ready", data: body, error: null });
      } catch (err) {
        if (err.name === "AbortError") return;
        setResult({ status: "error", data: null, error: err.message || "Something went wrong." });
      }
    },
    [router],
  );

  // Initial load: restore a shared URL's search, or show the default example.
  useEffect(() => {
    if (!router.isReady || started.current) return;
    started.current = true;
    const q = typeof router.query.q === "string" ? router.query.q : DEFAULT_QUERY;
    const p = typeof router.query.profile === "string" ? router.query.profile : router.query.q ? "general" : DEFAULT_PROFILE;
    const params = {
      query: q,
      profile: PROFILE_ORDER.includes(p) ? p : "general",
      department: typeof router.query.dept === "string" ? router.query.dept : "",
      maxPrice: typeof router.query.max === "string" ? router.query.max : "",
      minRating: typeof router.query.rating === "string" ? router.query.rating : "",
    };
    setQuery(params.query);
    setProfile(params.profile);
    setDepartment(params.department);
    setMaxPrice(params.maxPrice);
    setMinRating(params.minRating);
    search(params);
  }, [router.isReady, router.query, search]);

  useEffect(() => {
    fetch("/api/catalog")
      .then((r) => (r.ok ? r.json() : null))
      .then(setCatalog)
      .catch(() => setCatalog(null));
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : null))
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  const current = { query, profile, department, maxPrice, minRating };
  const rerun = (changes) => {
    const next = { ...current, ...changes };
    if (next.query.trim()) search(next);
  };
  const onSubmit = (e) => {
    e.preventDefault();
    search(current);
  };

  const data = result.data;
  const profiles = catalog?.profiles;
  const loading = result.status === "loading";

  return (
    <>
      <Head>
        <title>Aisle — explainable product recommendations</title>
        <meta
          name="description"
          content="Search a 33k-product Amazon India catalog snapshot with hybrid semantic + keyword ranking, shopper profiles and per-result explanations."
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
      </Head>

      <header className={styles.topbar}>
        <div className={styles.topbarInner}>
          <Link href="/" className={styles.wordmark} aria-label="Aisle home">
            <span className={styles.wordmarkMark} aria-hidden="true">
              ▤
            </span>
            Aisle
          </Link>
          <EngineBadge health={health} />
        </div>
      </header>

      <main className={styles.page}>
        <section className={styles.hero}>
          <h1>Find the right product — and see why it ranks.</h1>
          <p className={styles.lede}>
            Describe what you need in plain words, budgets included. Results blend meaning, keywords, ratings and your
            shopper profile, and every one comes with its reasons.
          </p>

          <form role="search" className={styles.searchForm} onSubmit={onSubmit}>
            <label htmlFor="query" className="visually-hidden">
              What are you looking for?
            </label>
            <input
              id="query"
              className={styles.searchInput}
              type="search"
              value={query}
              maxLength={200}
              autoComplete="off"
              placeholder="e.g. wireless earbuds under 2000"
              onChange={(e) => setQuery(e.target.value)}
            />
            <button type="submit" className={styles.primaryButton} disabled={!query.trim()}>
              Search
            </button>
          </form>

          <div className={styles.controls}>
            <fieldset className={styles.segmented}>
              <legend className={styles.controlLabel}>Shopper profile</legend>
              <div className={styles.segmentedOptions}>
                {PROFILE_ORDER.map((id) => (
                  <label key={id} className={styles.segment} title={profiles?.[id]?.description}>
                    <input
                      type="radio"
                      name="profile"
                      value={id}
                      checked={profile === id}
                      onChange={() => {
                        setProfile(id);
                        rerun({ profile: id });
                      }}
                    />
                    <span>{profiles?.[id]?.label || id}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <div className={styles.filters}>
              <label className={styles.filter}>
                <span className={styles.controlLabel}>Department</span>
                <select
                  value={department}
                  onChange={(e) => {
                    setDepartment(e.target.value);
                    rerun({ department: e.target.value });
                  }}
                >
                  <option value="">All departments</option>
                  {catalog?.departments.map((d) => (
                    <option key={d.name} value={d.name}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className={styles.filter}>
                <span className={styles.controlLabel}>Max price (₹)</span>
                <input
                  type="number"
                  inputMode="numeric"
                  min="0"
                  step="100"
                  placeholder="No limit"
                  value={maxPrice}
                  onChange={(e) => setMaxPrice(e.target.value)}
                  onBlur={() => rerun({})}
                  onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), rerun({}))}
                />
              </label>
              <label className={styles.filter}>
                <span className={styles.controlLabel}>Rating</span>
                <select
                  value={minRating}
                  onChange={(e) => {
                    setMinRating(e.target.value);
                    rerun({ minRating: e.target.value });
                  }}
                >
                  {RATING_OPTIONS.map(([v, label]) => (
                    <option key={v} value={v}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          <div className={styles.samples}>
            <span className={styles.controlLabel}>Try</span>
            <ul>
              {SAMPLE_QUERIES.map((s) => (
                <li key={s}>
                  <button
                    type="button"
                    className={styles.sample}
                    onClick={() => {
                      setQuery(s);
                      search({ ...current, query: s });
                    }}
                  >
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <div className={styles.layout}>
          <section className={styles.resultsColumn} aria-labelledby="results-title" aria-busy={loading}>
            <div className={styles.resultsHeader}>
              <h2 id="results-title">Recommendations</h2>
              <p className={styles.muted} role="status" aria-live="polite">
                {loading
                  ? "Ranking…"
                  : data
                    ? `${data.results.length} of ${data.total_matches.toLocaleString("en-IN")} relevant products · ${data.took_ms} ms`
                    : ""}
              </p>
            </div>

            {data?.engine?.notice && (
              <p className={data.engine.degraded ? styles.noticeWarn : styles.notice}>{data.engine.notice}</p>
            )}
            {data && <Interpretation data={data} profiles={profiles} />}

            {result.status === "error" && (
              <div className={styles.errorBox} role="alert">
                <p>{result.error}</p>
                <button type="button" className={styles.secondaryButton} onClick={() => search(current)}>
                  Try again
                </button>
              </div>
            )}

            {loading && !data && <SkeletonList />}

            {data && data.results.length === 0 && !loading && (
              <div className={styles.empty}>
                <p>{data.message || "Nothing in this catalog matches that search."}</p>
                <p className={styles.muted}>
                  Try fewer words, raise the budget, or clear the department and rating filters.
                </p>
              </div>
            )}

            {data && data.results.length > 0 && (
              <ol className={`${styles.results} ${loading ? styles.stale : ""}`}>
                {data.results.map((item, i) => (
                  <ResultCard key={`${data.query}-${item.asin}`} item={item} rank={i + 1} onShowSimilar={openSimilar} />
                ))}
              </ol>
            )}
          </section>

          <aside className={styles.sideColumn}>
            <CatalogInsights catalog={catalog} />
            <section className={styles.howItWorks} aria-labelledby="how-title">
              <h2 id="how-title">How ranking works</h2>
              <ol>
                <li>Your query is parsed for a product type, a budget and keywords.</li>
                <li>Candidates come from keyword search (BM25), semantic vector search and the product type.</li>
                <li>
                  Each candidate is scored on relevance, Bayesian-smoothed rating, popularity, discount and profile fit.
                </li>
                <li>Colour and size variants are collapsed, and every result lists the signals behind it.</li>
              </ol>
            </section>
          </aside>
        </div>
      </main>

      <footer className={styles.footer}>
        <p>
          Independent portfolio project, not affiliated with Amazon. Product data comes from a public Amazon India listings
          export ({catalog?.snapshot || "2023"}); prices, ratings and availability may have changed.
        </p>
      </footer>

      {similarFor && (
        <SimilarDrawer product={similarFor} onClose={closeSimilar} onPick={setSimilarFor} />
      )}
    </>
  );
}
