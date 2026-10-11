import { SIGNAL_LABELS } from "../lib/format.mjs";
import styles from "../styles/app.module.css";

// Stacked bar of each signal's weighted contribution to the final score (0–1).
export default function ScoreBreakdown({ contributions, signals }) {
  const entries = Object.entries(contributions).filter(([, v]) => v > 0);
  return (
    <figure className={styles.breakdown}>
      <div className={styles.breakdownBar} role="img" aria-label="Score contributions by signal">
        {entries.map(([name, value]) => (
          <span
            key={name}
            className={styles.breakdownSegment}
            style={{ width: `${value * 100}%`, background: `var(--sig-${name})` }}
            title={`${SIGNAL_LABELS[name]}: +${value.toFixed(3)}`}
          />
        ))}
      </div>
      <figcaption>
        <dl className={styles.breakdownLegend}>
          {Object.keys(SIGNAL_LABELS).map((name) => (
            <div key={name} className={styles.breakdownItem}>
              <dt>
                <span className={styles.swatch} style={{ background: `var(--sig-${name})` }} aria-hidden="true" />
                {SIGNAL_LABELS[name]}
              </dt>
              <dd>
                {(signals[name] ?? 0).toFixed(2)}
                <span className={styles.muted}> → +{(contributions[name] ?? 0).toFixed(3)}</span>
              </dd>
            </div>
          ))}
          {signals.semantic !== null && signals.semantic !== undefined && (
            <div className={styles.breakdownItem}>
              <dt>Semantic match</dt>
              <dd>
                {signals.semantic.toFixed(2)}
                {signals.cosine != null && <span className={styles.muted}> (cos {signals.cosine.toFixed(2)})</span>}
              </dd>
            </div>
          )}
          <div className={styles.breakdownItem}>
            <dt>Keyword coverage</dt>
            <dd>{(signals.lexical ?? 0).toFixed(2)}</dd>
          </div>
        </dl>
      </figcaption>
    </figure>
  );
}
