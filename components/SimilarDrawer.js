import { useEffect, useRef, useState } from "react";

import styles from "../styles/app.module.css";
import ProductImage from "./ProductImage";
import { Price, Rating } from "./ResultCard";

// Item-to-item recommendations for one product, shown in a modal side panel.
export default function SimilarDrawer({ product, onClose, onPick }) {
  const [state, setState] = useState({ status: "loading", data: null, error: null });
  const closeRef = useRef(null);
  const drawerRef = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading", data: null, error: null });
    fetch(`/api/similar?asin=${encodeURIComponent(product.asin)}&k=8`, { signal: controller.signal })
      .then(async (res) => {
        const body = await res.json();
        if (!res.ok) throw new Error(body.error || `Request failed (${res.status})`);
        setState({ status: "ready", data: body, error: null });
      })
      .catch((err) => {
        if (err.name !== "AbortError") setState({ status: "error", data: null, error: err.message });
      });
    return () => controller.abort();
  }, [product.asin]);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e) => {
      if (e.key === "Escape") return onClose();
      if (e.key !== "Tab" || !drawerRef.current) return;
      // Keep keyboard focus inside the modal.
      const focusable = drawerRef.current.querySelectorAll("a[href], button:not([disabled])");
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  const engine = state.data?.engine;
  return (
    <div className={styles.overlay} onClick={onClose}>
      <aside
        ref={drawerRef}
        className={styles.drawer}
        role="dialog"
        aria-modal="true"
        aria-labelledby="similar-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className={styles.drawerHeader}>
          <div>
            <h2 id="similar-title">Similar items</h2>
            <p className={styles.drawerSubtitle}>{product.name}</p>
          </div>
          <button ref={closeRef} type="button" className={styles.iconButton} onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>
        {state.status === "loading" && <p className={styles.muted}>Finding neighbours…</p>}
        {state.status === "error" && (
          <p className={styles.errorInline} role="alert">
            {state.error}
          </p>
        )}
        {state.status === "ready" && (
          <>
            <p className={styles.drawerNote}>
              {engine?.mode === "hybrid"
                ? `Nearest neighbours in embedding space (${engine.model?.split("/").pop()}).`
                : engine?.notice || "Matched by keyword overlap."}
            </p>
            {state.data.results.length === 0 ? (
              <p className={styles.muted}>No close matches in this catalog.</p>
            ) : (
              <ul className={styles.similarList}>
                {state.data.results.map((item) => (
                  <li key={item.asin} className={styles.similarItem}>
                    <ProductImage src={item.image_url} size={72} />
                    <div>
                      <a href={item.product_url} target="_blank" rel="noopener noreferrer" className={styles.similarName}>
                        {item.name}
                      </a>
                      <div className={styles.cardMeta}>
                        <Price price={item.price} listPrice={item.list_price} discount={item.discount_pct} />
                        <Rating rating={item.rating} count={item.rating_count} />
                      </div>
                      <button type="button" className={styles.linkButton} onClick={() => onPick(item)}>
                        Items like this
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </aside>
    </div>
  );
}
