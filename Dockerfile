# Python semantic API (api_server.py). Build context: repository root.
#   docker build -t rec-engine-api .
#   docker run -p 8000:8000 rec-engine-api
# The image bakes in the embedding model and the product embeddings, so it starts
# without network access. Needs ~1 GB RAM at runtime.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

# CPU-only PyTorch keeps the image ~1.5 GB smaller than the default CUDA build.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.5.1
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY config ./config
COPY src ./src
COPY scripts/__init__.py scripts/build_index.py ./scripts/
COPY data/processed/catalog.json data/processed/catalog_meta.json ./data/processed/
COPY api_server.py .

# Download the model and encode the catalog at build time (a few minutes on CPU).
RUN python -m scripts.build_index

RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

ENV HF_HUB_OFFLINE=1 \
    AUTO_BUILD_INDEX=false \
    PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/ready', timeout=4)"
CMD ["sh", "-c", "exec uvicorn api_server:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers"]
