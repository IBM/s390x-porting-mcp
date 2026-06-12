#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

WIKI_DIR=""
SCRIPTS_DIR=""
SKIP_DOCKER=false
REGISTRY=""
CLONE_SOURCES=false

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Regenerate the s390x MCP knowledge base from upstream sources.

Options:
  --wiki-dir DIR       Path to cloned linux-on-ibm-z/docs.wiki.git
  --scripts-dir DIR    Path to cloned linux-on-ibm-z/scripts.git
  --clone              Clone sources to /tmp instead of requiring --wiki-dir/--scripts-dir
  --skip-docker        Skip Docker image build and push
  --registry URL       Docker registry to push to (e.g., registry.example.com/s390x-mcp)
  -h, --help           Show this help message

Examples:
  # Local update with pre-cloned repos
  $(basename "$0") --wiki-dir /tmp/wiki --scripts-dir /tmp/scripts --skip-docker

  # Full pipeline with fresh clones
  $(basename "$0") --clone --registry registry.example.com/s390x-mcp

  # CI mode: clone, build, push
  $(basename "$0") --clone --registry \$DOCKER_REGISTRY
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --wiki-dir)    WIKI_DIR="$2"; shift 2 ;;
        --scripts-dir) SCRIPTS_DIR="$2"; shift 2 ;;
        --clone)       CLONE_SOURCES=true; shift ;;
        --skip-docker) SKIP_DOCKER=true; shift ;;
        --registry)    REGISTRY="$2"; shift 2 ;;
        -h|--help)     usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

if [[ "$CLONE_SOURCES" == true ]]; then
    echo "==> Cloning upstream sources..."
    if [[ -d /tmp/wiki/.git ]]; then
        git -C /tmp/wiki pull --ff-only
    else
        rm -rf /tmp/wiki
        git clone --depth 1 https://github.com/linux-on-ibm-z/docs.wiki.git /tmp/wiki
    fi
    if [[ -d /tmp/scripts/.git ]]; then
        git -C /tmp/scripts pull --ff-only
    else
        rm -rf /tmp/scripts
        git clone --depth 1 https://github.com/linux-on-ibm-z/scripts.git /tmp/scripts
    fi
    WIKI_DIR=/tmp/wiki
    SCRIPTS_DIR=/tmp/scripts
fi

if [[ -z "$WIKI_DIR" || -z "$SCRIPTS_DIR" ]]; then
    echo "ERROR: --wiki-dir and --scripts-dir are required (or use --clone)"
    exit 1
fi

if [[ ! -d "$WIKI_DIR" ]]; then
    echo "ERROR: Wiki directory not found: $WIKI_DIR"
    exit 1
fi

if [[ ! -d "$SCRIPTS_DIR" ]]; then
    echo "ERROR: Scripts directory not found: $SCRIPTS_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

# Step 1: Generate chunks
echo "==> Generating chunks..."
python3 embedding-generation/generate_chunks.py \
    --wiki-dir "$WIKI_DIR" \
    --scripts-dir "$SCRIPTS_DIR" \
    --output-dir embedding-generation/output \
    --script-index-output mcp-server/data/script_index.json

# Step 2: Generate vector index
echo "==> Generating vector index..."
python3 embedding-generation/local_vectorstore_creation.py \
    --metadata embedding-generation/output/metadata.json \
    --output-dir mcp-server/data

# Step 3: Evaluate search quality
echo "==> Evaluating search quality..."
EVAL_OUTPUT=$(bash embedding-generation/run_eval.sh 2>&1)
echo "$EVAL_OUTPUT"

HIT1=$(echo "$EVAL_OUTPUT" | sed -n 's/.*Hit@1: \([0-9.]*\).*/\1/p')
HIT3=$(echo "$EVAL_OUTPUT" | sed -n 's/.*Hit@3: \([0-9.]*\).*/\1/p')
MRR=$(echo "$EVAL_OUTPUT" | sed -n 's/.*MRR: *\([0-9.]*\).*/\1/p')

QUALITY_FAILED=false

if [[ -n "$HIT1" ]] && python3 -c "exit(0 if float('$HIT1') >= 0.60 else 1)" 2>/dev/null; then
    echo "  Hit@1: $HIT1 >= 0.60 OK"
else
    echo "  Hit@1: ${HIT1:-N/A} < 0.60 FAIL"
    QUALITY_FAILED=true
fi

if [[ -n "$HIT3" ]] && python3 -c "exit(0 if float('$HIT3') >= 0.80 else 1)" 2>/dev/null; then
    echo "  Hit@3: $HIT3 >= 0.80 OK"
else
    echo "  Hit@3: ${HIT3:-N/A} < 0.80 FAIL"
    QUALITY_FAILED=true
fi

if [[ -n "$MRR" ]] && python3 -c "exit(0 if float('$MRR') >= 0.70 else 1)" 2>/dev/null; then
    echo "  MRR:   $MRR >= 0.70 OK"
else
    echo "  MRR:   ${MRR:-N/A} < 0.70 FAIL"
    QUALITY_FAILED=true
fi

if [[ "$QUALITY_FAILED" == true ]]; then
    echo "ERROR: Search quality below thresholds. Aborting."
    exit 1
fi

# Step 4: Run tests
echo "==> Running tests..."
python3 -m pytest mcp-server/tests/ -v

# Step 5: Docker build (optional)
if [[ "$SKIP_DOCKER" == true ]]; then
    echo "==> Skipping Docker build (--skip-docker)"
else
    echo "==> Building Docker images..."
    docker build -t s390x-mcp:embeddings-latest -f embedding-generation/Dockerfile .
    docker build -t s390x-mcp:latest -f mcp-server/Dockerfile .

    if [[ -n "$REGISTRY" ]]; then
        TAG="${REGISTRY}:latest"
        echo "==> Pushing $TAG..."
        docker tag s390x-mcp:latest "$TAG"
        docker push "$TAG"
    fi
fi

echo "==> Knowledge base update complete."
