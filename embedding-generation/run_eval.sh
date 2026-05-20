#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

METADATA="${1:-$PROJECT_DIR/mcp-server/data/metadata.json}"
INDEX="${2:-$PROJECT_DIR/mcp-server/data/usearch_index.bin}"
EVAL_QUESTIONS="$SCRIPT_DIR/eval_questions.json"

if [ ! -f "$METADATA" ]; then
    echo "ERROR: Metadata file not found: $METADATA"
    echo "Run generate_chunks.py and local_vectorstore_creation.py first."
    exit 1
fi

cd "$PROJECT_DIR"

python3 -c "
import json
import sys
sys.path.insert(0, '.')
from s390x_kb_search import load_search_resources
from s390x_kb_search.evaluation import run_evaluation

resources = load_search_resources('$METADATA', '$INDEX')
results = run_evaluation('$EVAL_QUESTIONS', resources)

print()
print('=== Search Quality Report ===')
print(f'Questions evaluated: {results[\"evaluated\"]}')
print(f'Hit@1: {results[\"hit_at_1\"]:.4f} (target >= 0.60)')
print(f'Hit@3: {results[\"hit_at_3\"]:.4f} (target >= 0.80)')
print(f'Hit@5: {results[\"hit_at_5\"]:.4f}')
print(f'MRR:   {results[\"mrr\"]:.4f} (target >= 0.70)')
print()

failed = []
for d in results['details']:
    if d['first_hit_rank'] is None:
        failed.append(d)

if failed:
    print(f'{len(failed)} questions missed:')
    for d in failed:
        print(f'  - {d[\"id\"]}: {d[\"question\"]}')
        print(f'    Expected: {d[\"expected_urls\"]}')
        print(f'    Got:      {d[\"result_urls\"][:3]}')
"
