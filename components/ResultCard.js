import { useId, useState } from "react";

import { formatCount, formatInr } from "../lib/format.mjs";
import styles from "../styles/app.module.css";
import ProductImage from "./ProductImage";
import ScoreBreakdown from "./ScoreBreakdown";

export function Rating({ rating, count }) {
  return (
    <span className={styles.rating}>
      <span className={styles.star} aria-hidden="true">
        ★
      </span>
      <span>
        {rating.toFixed(1)}
        <span className="visually-hidden"> out of 5 stars from {count.toLocaleString("en-IN")} ratings</span>
      </span>
      <span className={styles.muted} aria-hidden="true">
        ({formatCount(count)})
      </span>
    </span>
  );
}

export function Price({ price, listPrice, discount }) {
  return (
    <span className={styles.priceRow}>
      <span className={styles.price}>{formatInr(price)}</span>
      {discount > 0 && (
        <>
          <s className={styles.listPrice}>
            <span className="visually-hidden">List price </span>
            {formatInr(listPrice)}
          </s>
          <span className={styles.discount}>−{discount}%</span>
        </>
      )}
    </span>
  );
}

export default function ResultCard({ item, rank, onShowSimilar }) {
  const [open, setOpen] = useState(rank === 1);
  const panelId = useId();
  return (
    <li className={styles.card}>
      <div className={styles.cardMedia}>
        <ProductImage src={item.image_url} size={132} />
      </div>
      <div className={styles.cardBody}>
        <p className={styles.crumb}>
          <span className={styles.rank}>#{rank}</span>
          {item.main_category} › {item.sub_category}
        </p>
        <h3 className={styles.cardTitle}>
          <a href={item.product_url} target="_blank" rel="noopener noreferrer">
            {item.name}
            <span className="visually-hidden"> (opens amazon.in in a new tab)</span>
          </a>
        </h3>
        <div className={styles.cardMeta}>
          <Price price={item.price} listPrice={item.list_price} discount={item.discount_pct} />
          <Rating rating={item.rating} count={item.rating_count} />
          <span className={styles.scorePill} title="Final ranking score (0–1)">
            score {item.score.toFixed(3)}
          </span>
        </div>
        {item.reasons?.length > 0 && <p className={styles.reasonLead}>{item.reasons[0]}</p>}
        <div className={styles.cardActions}>
          <button
            type="button"
            className={styles.linkButton}
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? "Hide" : "Why this?"}
          </button>
          <button type="button" className={styles.linkButton} onClick={(e) => onShowSimilar(item, e.currentTarget)}>
            Similar items
          </button>
        </div>
        {open && (
          <div id={panelId} className={styles.why}>
            <ul className={styles.reasons}>
              {item.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
            <ScoreBreakdown contributions={item.contributions} signals={item.signals} />
          </div>
        )}
      </div>
    </li>
  );
}
