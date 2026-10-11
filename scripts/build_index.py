"""Encode every catalog product and write models/embeddings.npy + models/manifest.json.

Usage: python -m scripts.build_index [--force]

Skips work when the existing artifact already matches the catalog and model.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import embeddings as emb  # noqa: E402
from src.catalog import load_catalog  # noqa: E402
from src.config import load_engine_config, load_settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="rebuild even if the artifact is current")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = load_settings()
    catalog = load_catalog(settings.catalog_path, load_engine_config())
    if not args.force:
        try:
            emb.load_embeddings(catalog, settings.embedding_model, settings.embeddings_path, settings.manifest_path)
            print(f"Embeddings are current for {len(catalog):,} products; nothing to do (use --force to rebuild).")
            return
        except emb.StaleEmbeddingsError as exc:
            print(exc)

    started = time.perf_counter()
    encoder = emb.SentenceTransformerEncoder(settings.embedding_model)
    vectors = emb.build_embeddings(catalog, encoder)
    emb.save_embeddings(vectors, catalog, settings.embedding_model, settings.embeddings_path, settings.manifest_path)
    print(
        f"Encoded {len(catalog):,} products ({vectors.shape[1]}-d) in {time.perf_counter() - started:.0f}s "
        f"-> {settings.embeddings_path.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
