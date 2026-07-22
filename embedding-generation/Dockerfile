FROM ubuntu:24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip python3-dev \
    build-essential \
    git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV VIRTUAL_ENV=/app/.venv PATH=/app/.venv/bin:$PATH
RUN python3 -m venv "$VIRTUAL_ENV" && pip install --upgrade pip

COPY embedding-generation/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY embedding-generation/ ./embedding-generation/
COPY s390x_kb_search/ ./s390x_kb_search/

RUN mkdir -p /embedding-data

ENTRYPOINT ["python3", "embedding-generation/generate_chunks.py"]

FROM scratch AS output
COPY mcp-server/data/metadata.json /embedding-data/metadata.json
COPY mcp-server/data/usearch_index.bin /embedding-data/usearch_index.bin
