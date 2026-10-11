// Loads the shared catalog/config from disk once per server instance.

import fs from "node:fs";
import path from "node:path";

import { LexicalEngine } from "./engine.mjs";

export { InvalidRequestError, LexicalEngine, UnknownProductError } from "./engine.mjs";

const root = () => process.env.APP_ROOT || process.cwd();
export const paths = {
  catalog: () => path.join(root(), "data", "processed", "catalog.json"),
  catalogMeta: () => path.join(root(), "data", "processed", "catalog_meta.json"),
  config: () => path.join(root(), "config", "engine.json"),
};

const readJson = (file) => JSON.parse(fs.readFileSync(file, "utf-8"));

let cachedConfig = null;
export function getConfig() {
  if (!cachedConfig) cachedConfig = readJson(paths.config());
  return cachedConfig;
}

let cachedMeta = null;
export function getCatalogMeta() {
  if (!cachedMeta) cachedMeta = readJson(paths.catalogMeta());
  return cachedMeta;
}

let cachedEngine = null;
export function getLexicalEngine() {
  if (!cachedEngine) cachedEngine = new LexicalEngine(readJson(paths.catalog()), getConfig());
  return cachedEngine;
}
