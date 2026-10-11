import { useState } from "react";

import styles from "../styles/app.module.css";

// Product photos are hot-linked from Amazon's public image CDN; a neutral tile replaces any
// image that fails to load so a broken link never breaks the layout.
export default function ProductImage({ src, size = 160 }) {
  const [failed, setFailed] = useState(!src);
  if (failed) {
    return (
      <div className={styles.imageFallback} style={{ width: size, height: size }} aria-hidden="true">
        No image
      </div>
    );
  }
  return (
    // next/image would proxy every catalog photo through the image optimiser; plain lazy
    // <img> keeps the photos on Amazon's CDN and the deployment free of optimiser costs.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      className={styles.image}
      src={src}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}
