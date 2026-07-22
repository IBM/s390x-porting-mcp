ARG EMBEDDINGS_IMAGE=s390x-mcp:embeddings-latest

# Stage 0: Pre-built embeddings
FROM ${EMBEDDINGS_IMAGE} AS embeddings

# Stage 1: Builder
FROM ubuntu:24.04 AS builder

ARG EMBEDDING_MODEL=all-MiniLM-L6-v2
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    WORKSPACE_DIR=/workspace \
    HF_HOME=/app/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip python3-dev \
    build-essential \
    curl git wget ca-certificates skopeo && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV VIRTUAL_ENV=/app/.venv PATH=/app/.venv/bin:$PATH
RUN python3 -m venv "$VIRTUAL_ENV" && pip install --upgrade pip

COPY mcp-server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p "$HF_HOME" "$SENTENCE_TRANSFORMERS_HOME" && \
    python3 -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('${EMBEDDING_MODEL}', cache_folder='${SENTENCE_TRANSFORMERS_HOME}')"

RUN mkdir -p ./data
COPY --from=embeddings /embedding-data/metadata.json ./data/metadata.json
COPY --from=embeddings /embedding-data/usearch_index.bin ./data/usearch_index.bin
COPY mcp-server/data/script_index.json ./data/script_index.json

COPY mcp-server/patterns/ ./patterns/
COPY mcp-server/utils/ ./utils/
COPY s390x_kb_search/ ./s390x_kb_search/
COPY mcp-server/server.py .

# Stage 2: Runtime
FROM ubuntu:24.04 AS runtime
LABEL io.modelcontextprotocol.server.name="s390x-mcp"
LABEL io.modelcontextprotocol.server.version="0.1.0"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    WORKSPACE_DIR=/workspace \
    VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    HF_HOME=/app/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers \
    HF_HUB_OFFLINE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 ca-certificates skopeo git && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app
WORKDIR /app
VOLUME ["/workspace"]
ENTRYPOINT ["python3", "-u", "server.py"]
