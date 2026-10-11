import styles from "../styles/app.module.css";

function BarList({ rows, label }) {
  const max = Math.max(...rows.map((r) => r.count), 1);
  return (
    <ul className={styles.barList} aria-label={label}>
      {rows.map((row) => (
        <li key={row.name}>
          <span className={styles.barLabel}>{row.name}</span>
          <span className={styles.barTrack} aria-hidden="true">
            <span className={styles.barFill} style={{ width: `${(row.count / max) * 100}%` }} />
          </span>
          <span className={styles.barValue}>{row.count.toLocaleString("en-IN")}</span>
        </li>
      ))}
    </ul>
  );
}

// What the engine is searching over: size, snapshot date and composition of the catalog.
export default function CatalogInsights({ catalog }) {
  if (!catalog) return null;
  const ratings = Object.entries(catalog.rating_histogram || {})
    .map(([name, count]) => ({ name: `${name}★`, count }))
    .filter((r) => parseFloat(r.name) >= 3);
  return (
    <section className={styles.insights} aria-labelledby="insights-title">
      <h2 id="insights-title">About this catalog</h2>
      <p className={styles.muted}>
        {catalog.total_products.toLocaleString("en-IN")} products from Amazon India listings captured in{" "}
        {catalog.snapshot || "2023"}. Prices and ratings are from that snapshot, not live.
      </p>
      <div className={styles.insightGrid}>
        <div>
          <h3>Departments</h3>
          <BarList label="Products per department" rows={catalog.departments.slice(0, 10)} />
        </div>
        <div>
          <h3>Price bands</h3>
          <BarList label="Products per price band" rows={catalog.price_bands.map((b) => ({ name: b.label, count: b.count }))} />
          <h3>Ratings</h3>
          <BarList label="Products per star rating" rows={ratings} />
        </div>
      </div>
    </section>
  );
}
