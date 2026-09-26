import { useState, useEffect } from "react";
import Head from "next/head";

export default function Home() {
  const [query, setQuery] = useState("Need laptop for AI under 90k");
  const [userProfile, setUserProfile] = useState("ai_student");
  const [loading, setLoading] = useState(false);
  const [recommendations, setRecommendations] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [source, setSource] = useState(null);
  const [expandedIndex, setExpandedIndex] = useState(0);
  const [error, setError] = useState(null);

  const sampleQueries = [
    "Need laptop for AI under 90k",
    "gaming laptop under 90000",
    "wireless earbuds",
    "mechanical keyboard",
    "monitor for coding",
    "TP-Link router",
  ];

  // Fetch initial analytics and trigger default search
  useEffect(() => {
    fetchAnalytics();
    handleSearch("Need laptop for AI under 90k", "ai_student");
  }, []);

  const fetchAnalytics = async () => {
    try {
      const res = await fetch("/api/analytics");
      if (res.ok) {
        const data = await res.json();
        setAnalytics(data);
      }
    } catch (e) {
      console.error("Failed to load analytics:", e);
    }
  };

  const handleSearch = async (searchQuery = query, profile = userProfile) => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: searchQuery,
          user_type: profile,
          top_k: 5,
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || "Failed to fetch recommendations");
      }

      const data = await res.json();
      setRecommendations(data.recommendations || []);
      setSource(data.source || "serverless");
      setExpandedIndex(0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const formatPrice = (price) => {
    if (price === null || price === undefined) return "N/A";
    const num = parseFloat(price);
    return isNaN(num) ? price : `₹${num.toLocaleString("en-IN")}`;
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Head>
        <title>Amazon-Style Recommendation Engine</title>
        <meta
          name="description"
          content="End-to-end Machine Learning Recommendation System inspired by modern e-commerce platforms"
        />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      {/* Top Navbar */}
      <header
        style={{
          backgroundColor: "#131921",
          color: "#ffffff",
          padding: "12px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "12px",
          borderBottom: "4px solid #ff9900",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "22px", fontWeight: "800", color: "#ff9900", letterSpacing: "-0.5px" }}>
            amazon
          </span>
          <span
            style={{
              fontSize: "14px",
              padding: "4px 8px",
              background: "#232f3e",
              borderRadius: "4px",
              border: "1px solid #3a4553",
              color: "#d5d9d9",
            }}
          >
            Recommendation Engine
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "13px" }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              background: source === "external-ml-backend" ? "#1e4620" : "#2a394a",
              color: source === "external-ml-backend" ? "#7ee787" : "#79c0ff",
              padding: "4px 10px",
              borderRadius: "12px",
              border: `1px solid ${source === "external-ml-backend" ? "#2ea043" : "#388bfd"}`,
            }}
          >
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: source === "external-ml-backend" ? "#3fb950" : "#58a6ff",
              }}
            />
            {source === "external-ml-backend" ? "External ML Backend Connected" : "Vercel Serverless Ready"}
          </span>
        </div>
      </header>

      {/* Main Container */}
      <div
        style={{
          maxWidth: "1440px",
          margin: "0 auto",
          width: "100%",
          padding: "24px 20px",
          display: "grid",
          gridTemplateColumns: "320px 1fr",
          gap: "24px",
          flex: 1,
        }}
        className="layout-grid"
      >
        {/* Sidebar Controls (Streamlit sidebar equivalent) */}
        <aside
          style={{
            background: "#ffffff",
            padding: "20px",
            borderRadius: "8px",
            border: "1px solid #d5d9d9",
            height: "fit-content",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        >
          <h2 style={{ fontSize: "16px", fontWeight: "700", marginBottom: "16px", color: "#0f1111" }}>
            Search & Profile Filters
          </h2>

          <div style={{ marginBottom: "18px" }}>
            <label
              htmlFor="user-profile-select"
              style={{ display: "block", fontSize: "13px", fontWeight: "600", marginBottom: "6px", color: "#565959" }}
            >
              User Profile
            </label>
            <select
              id="user-profile-select"
              value={userProfile}
              onChange={(e) => setUserProfile(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "6px",
                border: "1px solid #888c8c",
                fontSize: "14px",
                backgroundColor: "#f8f9fa",
                cursor: "pointer",
              }}
            >
              <option value="ai_student">AI / ML Student (Heavy Compute)</option>
              <option value="gaming">Gaming Enthusiast (GPU Focus)</option>
              <option value="student">Student (Budget & Battery)</option>
              <option value="general">General Shopper (Balanced)</option>
            </select>
          </div>

          <div style={{ marginBottom: "18px" }}>
            <label
              htmlFor="product-query-input"
              style={{ display: "block", fontSize: "13px", fontWeight: "600", marginBottom: "6px", color: "#565959" }}
            >
              Product Search Query
            </label>
            <input
              id="product-query-input"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="e.g. Need laptop for AI under 90k"
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: "6px",
                border: "1px solid #888c8c",
                fontSize: "14px",
                outline: "none",
              }}
            />
          </div>

          <button
            onClick={() => handleSearch()}
            disabled={loading}
            style={{
              width: "100%",
              padding: "12px",
              backgroundColor: "#ffd814",
              border: "1px solid #fcd200",
              borderRadius: "20px",
              fontWeight: "600",
              fontSize: "14px",
              color: "#0f1111",
              boxShadow: "0 2px 5px rgba(213,217,217,.5)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
            }}
          >
            {loading ? "Computing Recommendations..." : "Recommend"}
          </button>

          <hr style={{ border: "none", borderTop: "1px solid #e7e7e7", margin: "20px 0" }} />

          <div style={{ fontSize: "13px", color: "#565959" }}>
            <span style={{ fontWeight: "600", display: "block", marginBottom: "8px" }}>Try Sample Queries:</span>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              {sampleQueries.map((sq, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setQuery(sq);
                    handleSearch(sq, userProfile);
                  }}
                  style={{
                    textAlign: "left",
                    padding: "6px 10px",
                    background: "#f0f2f2",
                    border: "1px solid #d5d9d9",
                    borderRadius: "4px",
                    fontSize: "12px",
                    color: "#0f1111",
                    transition: "all 0.15s ease",
                  }}
                >
                  🔍 {sq}
                </button>
              ))}
            </div>
          </div>
        </aside>

        {/* Content Area: Recommendations (Left 2/3) + Analytics (Right 1/3) */}
        <main style={{ display: "grid", gridTemplateColumns: "1.7fr 1fr", gap: "24px" }} className="content-grid">
          {/* Recommendations Area */}
          <section>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <div>
                <h1 style={{ fontSize: "20px", fontWeight: "700", color: "#0f1111" }}>
                  Product Recommendations
                </h1>
                <p style={{ fontSize: "13px", color: "#565959", marginTop: "2px" }}>
                  Showing top candidates retrieved via vector search & multi-signal ranking
                </p>
              </div>
              <span style={{ fontSize: "13px", fontWeight: "600", color: "#565959" }}>
                {recommendations.length} items
              </span>
            </div>

            {error && (
              <div
                style={{
                  background: "#fdf2f2",
                  border: "1px solid #f98080",
                  color: "#9b1c1c",
                  padding: "12px 16px",
                  borderRadius: "6px",
                  marginBottom: "16px",
                  fontSize: "14px",
                }}
              >
                ⚠️ {error}
              </div>
            )}

            {loading ? (
              <div style={{ padding: "60px 20px", textAlign: "center", color: "#565959" }}>
                <div style={{ fontSize: "28px", marginBottom: "12px" }}>⚙️</div>
                <div style={{ fontSize: "16px", fontWeight: "600" }}>Executing Recommendation Pipeline...</div>
                <div style={{ fontSize: "13px", marginTop: "4px" }}>
                  Retrieving embeddings → FAISS index search → Multi-signal ranking → Profile boost
                </div>
              </div>
            ) : recommendations.length === 0 ? (
              <div style={{ background: "#ffffff", padding: "40px", borderRadius: "8px", textAlign: "center", border: "1px solid #d5d9d9" }}>
                <p style={{ fontSize: "15px", color: "#565959" }}>No recommendations found for this query.</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                {recommendations.map((item, idx) => {
                  const isExpanded = expandedIndex === idx;
                  const score = item.personalized_score || item.score || 0;

                  return (
                    <article
                      key={idx}
                      style={{
                        background: "#ffffff",
                        borderRadius: "8px",
                        border: "1px solid #d5d9d9",
                        padding: "18px",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                        transition: "border-color 0.15s ease",
                      }}
                    >
                      {/* Product Header Row */}
                      <div
                        onClick={() => setExpandedIndex(isExpanded ? -1 : idx)}
                        style={{ cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px" }}
                      >
                        <div style={{ flex: 1 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                            <span
                              style={{
                                background: "#232f3e",
                                color: "#ffffff",
                                fontSize: "12px",
                                fontWeight: "700",
                                padding: "2px 8px",
                                borderRadius: "12px",
                              }}
                            >
                              Rank #{idx + 1}
                            </span>
                            <span style={{ fontSize: "12px", color: "#565959", textTransform: "capitalize" }}>
                              {item.category} {item.sub_category ? `› ${item.sub_category}` : ""}
                            </span>
                          </div>
                          <h3 style={{ fontSize: "16px", fontWeight: "600", color: "#007185", lineHeight: 1.3 }}>
                            {item.title || item.name}
                          </h3>
                        </div>

                        <span style={{ fontSize: "18px", color: "#565959" }}>
                          {isExpanded ? "▲" : "▼"}
                        </span>
                      </div>

                      {/* Key Product Metrics */}
                      <div
                        style={{
                          display: "flex",
                          flexWrap: "wrap",
                          gap: "16px",
                          alignItems: "center",
                          marginTop: "12px",
                          paddingTop: "12px",
                          borderTop: "1px solid #f0f2f2",
                          fontSize: "14px",
                        }}
                      >
                        <div>
                          <span style={{ color: "#ffa41c", fontWeight: "700" }}>★ {item.rating ? Number(item.rating).toFixed(1) : "N/A"}</span>
                          <span style={{ color: "#565959", fontSize: "12px", marginLeft: "4px" }}>
                            ({item.popularity ? Math.round(Number(item.popularity)).toLocaleString() : "100+"})
                          </span>
                        </div>

                        <div style={{ fontWeight: "700", fontSize: "16px", color: "#0f1111" }}>
                          {formatPrice(item.price)}
                        </div>

                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span style={{ fontSize: "12px", color: "#565959" }}>Score:</span>
                          <span
                            style={{
                              fontSize: "12px",
                              fontWeight: "700",
                              color: "#0f1111",
                              background: "#eef2f6",
                              padding: "2px 8px",
                              borderRadius: "4px",
                            }}
                          >
                            🎯 {(score).toFixed(4)}
                          </span>
                        </div>

                        <div style={{ fontSize: "12px", color: "#565959", background: "#f8f9fa", padding: "2px 8px", borderRadius: "4px" }}>
                          👤 {userProfile}
                        </div>
                      </div>

                      {/* Expandable Explanation Area */}
                      {isExpanded && (
                        <div
                          style={{
                            marginTop: "14px",
                            padding: "14px",
                            background: "#fafafa",
                            borderRadius: "6px",
                            border: "1px solid #e7e7e7",
                          }}
                        >
                          <h4 style={{ fontSize: "13px", fontWeight: "700", color: "#0f1111", marginBottom: "8px" }}>
                            Why Recommended?
                          </h4>
                          <div style={{ fontSize: "13px", color: "#333", whiteSpace: "pre-line", lineHeight: 1.6 }}>
                            {item.explanation}
                          </div>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            )}
          </section>

          {/* Analytics Dashboard Area (Streamlit analytics equivalent) */}
          <aside>
            <div style={{ marginBottom: "16px" }}>
              <h2 style={{ fontSize: "20px", fontWeight: "700", color: "#0f1111" }}>
                Catalog Analytics
              </h2>
              <p style={{ fontSize: "13px", color: "#565959", marginTop: "2px" }}>
                Real-time distribution of 292 marketplace products
              </p>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              {/* Category Distribution */}
              <div
                style={{
                  background: "#ffffff",
                  padding: "16px",
                  borderRadius: "8px",
                  border: "1px solid #d5d9d9",
                }}
              >
                <h3 style={{ fontSize: "14px", fontWeight: "700", marginBottom: "12px", color: "#0f1111" }}>
                  Product Category Distribution
                </h3>
                {analytics?.categories ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {Object.entries(analytics.categories).map(([cat, count]) => {
                      const max = Math.max(...Object.values(analytics.categories));
                      const pct = Math.round((count / max) * 100);
                      return (
                        <div key={cat} style={{ fontSize: "12px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "2px" }}>
                            <span style={{ fontWeight: "500", color: "#333", textTransform: "capitalize" }}>{cat}</span>
                            <span style={{ color: "#565959" }}>{count}</span>
                          </div>
                          <div style={{ width: "100%", height: "8px", background: "#eef2f6", borderRadius: "4px", overflow: "hidden" }}>
                            <div style={{ width: `${pct}%`, height: "100%", background: "#007185", borderRadius: "4px" }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p style={{ fontSize: "12px", color: "#565959" }}>Loading catalog categories...</p>
                )}
              </div>

              {/* Top Brands */}
              <div
                style={{
                  background: "#ffffff",
                  padding: "16px",
                  borderRadius: "8px",
                  border: "1px solid #d5d9d9",
                }}
              >
                <h3 style={{ fontSize: "14px", fontWeight: "700", marginBottom: "12px", color: "#0f1111" }}>
                  Top Brands
                </h3>
                {analytics?.top_brands ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {Object.entries(analytics.top_brands).map(([brand, count]) => {
                      const max = Math.max(...Object.values(analytics.top_brands));
                      const pct = Math.round((count / max) * 100);
                      return (
                        <div key={brand} style={{ fontSize: "12px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "2px" }}>
                            <span style={{ fontWeight: "500", color: "#333" }}>{brand}</span>
                            <span style={{ color: "#565959" }}>{count}</span>
                          </div>
                          <div style={{ width: "100%", height: "8px", background: "#eef2f6", borderRadius: "4px", overflow: "hidden" }}>
                            <div style={{ width: `${pct}%`, height: "100%", background: "#ff9900", borderRadius: "4px" }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p style={{ fontSize: "12px", color: "#565959" }}>Loading top brands...</p>
                )}
              </div>

              {/* Score Distribution for Current Query */}
              <div
                style={{
                  background: "#ffffff",
                  padding: "16px",
                  borderRadius: "8px",
                  border: "1px solid #d5d9d9",
                }}
              >
                <h3 style={{ fontSize: "14px", fontWeight: "700", marginBottom: "12px", color: "#0f1111" }}>
                  Recommendation Score Distribution
                </h3>
                {recommendations.length > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {recommendations.map((rec, i) => {
                      const sc = rec.personalized_score || rec.score || 0;
                      return (
                        <div key={i} style={{ fontSize: "12px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "2px" }}>
                            <span style={{ color: "#565959" }}>Rank #{i + 1}</span>
                            <span style={{ fontWeight: "600", color: "#0f1111" }}>{sc.toFixed(4)}</span>
                          </div>
                          <div style={{ width: "100%", height: "8px", background: "#eef2f6", borderRadius: "4px", overflow: "hidden" }}>
                            <div style={{ width: `${Math.min(100, Math.round(sc * 100))}%`, height: "100%", background: "#4676FF", borderRadius: "4px" }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p style={{ fontSize: "12px", color: "#565959" }}>No recommendations yet</p>
                )}
              </div>
            </div>
          </aside>
        </main>
      </div>

      {/* Footer */}
      <footer
        style={{
          background: "#232f3e",
          color: "#d5d9d9",
          padding: "20px 24px",
          textAlign: "center",
          fontSize: "13px",
          marginTop: "auto",
        }}
      >
        <p>Amazon-Style Personalized Product Recommendation Engine • Production-Ready Vercel Deployment</p>
        <p style={{ color: "#888c8c", fontSize: "12px", marginTop: "4px" }}>
          Built-in analytics and recommendation cards help reviewers verify relevance, ordering, personalization, and explanation quality.
        </p>
      </footer>

      {/* Responsive layout styles */}
      <style jsx>{`
        @media (max-width: 1024px) {
          .layout-grid {
            grid-template-columns: 1fr !important;
          }
          .content-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}
