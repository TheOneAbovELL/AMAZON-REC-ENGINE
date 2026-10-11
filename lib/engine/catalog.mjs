// Columnar catalog (data/processed/catalog.json) -> product arrays. Mirrors src/catalog.py.

import { normalize, variantKey } from "./text.mjs";

export const CATALOG_COLUMNS = [
  "asin",
  "name",
  "main_category",
  "sub_category",
  "price",
  "list_price",
  "rating",
  "rating_count",
  "image_id",
];

export class CatalogError extends Error {}

export class Catalog {
  constructor(payload, config) {
    if (!payload || !Array.isArray(payload.columns) || !Array.isArray(payload.rows)) {
      throw new CatalogError("Catalog is not a valid columnar catalog.");
    }
    const missing = CATALOG_COLUMNS.filter((c) => !payload.columns.includes(c));
    if (missing.length) throw new CatalogError(`Catalog is missing columns: ${missing.join(", ")}`);
    if (!payload.rows.length) throw new CatalogError("Catalog contains no products.");

    const col = Object.fromEntries(CATALOG_COLUMNS.map((c) => [c, payload.columns.indexOf(c)]));
    const column = (name) => payload.rows.map((row) => row[col[name]]);
    this.asins = column("asin");
    this.names = column("name");
    this.mainCategories = column("main_category");
    this.subCategories = column("sub_category");
    this.imageIds = column("image_id");
    this.price = Float64Array.from(column("price"));
    this.listPrice = Float64Array.from(column("list_price"));
    this.rating = Float64Array.from(column("rating"));
    this.ratingCount = Float64Array.from(column("rating_count"));
    this.urls = config.urls;
    this.phraseMap = config.text.phrase_normalizations;
    this.position = new Map(this.asins.map((asin, i) => [asin, i]));
    this.normalizedNames = this.names.map((n) => normalize(n, this.phraseMap));
  }

  get length() {
    return this.asins.length;
  }

  indexText(i) {
    return `${this.names[i]} ${this.subCategories[i]} ${this.mainCategories[i]}`;
  }

  variantKeys(i, tokens) {
    const key = variantKey(this.normalizedNames[i], tokens);
    const brand = key.split(" ", 1)[0];
    return ["t:" + key, `p:${brand}|${Math.trunc(this.ratingCount[i])}|${this.rating[i].toFixed(1)}`];
  }

  record(i) {
    const price = this.price[i];
    const listPrice = this.listPrice[i];
    const discount = listPrice > price ? Math.floor((100 * (listPrice - price)) / listPrice + 0.5) : 0;
    const imageId = this.imageIds[i];
    return {
      asin: this.asins[i],
      name: this.names[i],
      main_category: this.mainCategories[i],
      sub_category: this.subCategories[i],
      price,
      list_price: listPrice,
      discount_pct: discount,
      rating: this.rating[i],
      rating_count: Math.trunc(this.ratingCount[i]),
      image_url: imageId ? this.urls.image.replace("{image_id}", imageId) : null,
      product_url: this.urls.product.replace("{asin}", this.asins[i]),
    };
  }
}
