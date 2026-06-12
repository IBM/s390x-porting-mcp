# Maintaining the s390x MCP Server

## Knowledge Pipeline Overview

```
Source Repos                    Offline Pipeline                     Runtime Artifacts
─────────────                   ────────────────                     ─────────────────
linux-on-ibm-z/docs.wiki ─┐
                           ├─► generate_chunks.py ─► metadata.json
linux-on-ibm-z/scripts ───┘                         chunks.yaml
                                     │               script_index.json
                                     ▼
                          local_vectorstore_creation.py
                                     │
                                     ▼
                           mcp-server/data/
                           ├── metadata.json      (~34 MB, chunk metadata)
                           ├── usearch_index.bin   (~25 MB, vector index)
                           └── script_index.json   (~667 KB, build script lookup)
                                     │
                                     ▼
                              Docker build
```

The two knowledge sources:

| Source | Content | Repo |
|--------|---------|------|
| **linux-on-ibm-z/docs wiki** | ~117 build guides (markdown) | `github.com/linux-on-ibm-z/docs.wiki.git` |
| **linux-on-ibm-z/scripts** | ~74 build scripts (shell) | `github.com/linux-on-ibm-z/scripts.git` |

## Updating the Knowledge Base

### Step 1: Get fresh source data

```bash
git clone --depth 1 https://github.com/linux-on-ibm-z/docs.wiki.git /tmp/wiki
git clone --depth 1 https://github.com/linux-on-ibm-z/scripts.git /tmp/scripts
```

If you already have local clones, `git pull` instead of re-cloning.

### Step 2: Generate chunks

```bash
python embedding-generation/generate_chunks.py \
  --wiki-dir /tmp/wiki \
  --scripts-dir /tmp/scripts \
  --output-dir embedding-generation/output \
  --script-index-output mcp-server/data/script_index.json
```

Both `--*-dir` flags are optional. Omit a source to skip it (e.g., if only the wiki changed, you can pass just `--wiki-dir`). However, the vector index is rebuilt from scratch each time, so you typically want to include both sources to get a complete index.

**Outputs:**
- `embedding-generation/output/metadata.json` -- chunk metadata for all sources
- `embedding-generation/output/chunks.yaml` -- same data in YAML format
- `mcp-server/data/script_index.json` -- fast lookup table used by `build_script_generate`

### Step 3: Generate the vector index

```bash
python embedding-generation/local_vectorstore_creation.py \
  --metadata embedding-generation/output/metadata.json \
  --output-dir mcp-server/data
```

This embeds every chunk using `all-MiniLM-L6-v2` (384-dim vectors) and builds a USearch index.

**Outputs:**
- `mcp-server/data/usearch_index.bin` -- binary vector index (L2 squared distance, connectivity=16)
- `mcp-server/data/metadata.json` -- copied from input for runtime use

This step requires `sentence-transformers` and `usearch`. The model (~80 MB) downloads on first run and is cached in `~/.cache/huggingface/`.

### Step 4: Evaluate search quality

```bash
bash embedding-generation/run_eval.sh
```

This runs the test questions in `embedding-generation/eval_questions.json` against the new index.

**Metrics and targets:**
| Metric | Target | Meaning |
|--------|--------|---------|
| Hit@1 | >= 0.60 | Is the top result correct? |
| Hit@3 | >= 0.80 | Is the correct answer in the top 3? |
| Hit@5 | -- | Is the correct answer in the top 5? |
| MRR | >= 0.70 | Mean reciprocal rank |

If metrics drop after an update, check:
- Were new chunks split poorly? (too large or too small)
- Do stopwords or reranking signals in `s390x_kb_search/config.py` need updating?
- Are new eval questions needed for new content? Add them to `eval_questions.json`.

### Step 5: Rebuild the Docker images

```bash
# Rebuild the embeddings image (contains metadata.json and usearch_index.bin)
docker build -t s390x-mcp:embeddings-latest -f embedding-generation/Dockerfile .

# Rebuild the MCP server image (pulls embeddings from the image above)
docker build -t s390x-mcp:latest -f mcp-server/Dockerfile .
```

The server Dockerfile uses a multi-stage build that copies `metadata.json` and `usearch_index.bin` from the embeddings image, so the embeddings image must be built first.

### Step 6: Verify

```bash
python -m pytest mcp-server/tests/ -v
```

Then test the tools interactively via Claude Code or another MCP client.

## When to Update

- **Wiki and scripts repos** are updated when the linux-on-ibm-z community publishes new build guides or supports new software versions/distros. Watch or periodically check those repos.
- A reasonable cadence: **monthly, or when upstream repos have notable new content**.

## Quick Reference

Minimal command sequence for a routine update:

```bash
# 1. Pull latest sources
cd /tmp/wiki && git pull
cd /tmp/scripts && git pull

# 2. Regenerate everything
python embedding-generation/generate_chunks.py \
  --wiki-dir /tmp/wiki \
  --scripts-dir /tmp/scripts \
  --output-dir embedding-generation/output \
  --script-index-output mcp-server/data/script_index.json

python embedding-generation/local_vectorstore_creation.py \
  --metadata embedding-generation/output/metadata.json \
  --output-dir mcp-server/data

# 3. Validate
bash embedding-generation/run_eval.sh
python -m pytest mcp-server/tests/ -v

# 4. Ship
docker build -t s390x-mcp:embeddings-latest -f embedding-generation/Dockerfile .
docker build -t s390x-mcp:latest -f mcp-server/Dockerfile .
```

## Maintaining Other Components

### Endian/Architecture Patterns

Pattern files in `mcp-server/patterns/` are used by `endian_scan` and `port_analysis` at runtime. No re-embedding is needed when they change.

**Files:**
- `endian-patterns.txt` -- common endian patterns (network functions, bit shifts)
- `c-cpp-patterns.txt` -- C/C++ specific (bit fields, unions, packed structs)
- `go-patterns.txt` -- Go specific (build constraints, CGO)
- `java-patterns.txt` -- Java specific
- `python-patterns.txt` -- Python specific
- `endian-fixes.txt` -- recommended fix patterns (before/after code)

**Format:** `SEVERITY|REGEX_PATTERN|DESCRIPTION|LANGUAGES`

After editing, run:
```bash
python -m pytest mcp-server/tests/test_endian_scan.py -v
```

### Search Tuning

Key parameters in `s390x_kb_search/config.py`:

| Parameter | Default | Effect |
|-----------|---------|--------|
| `DISTANCE_THRESHOLD` | 1.1 | Max L2 distance for valid results. Lower = stricter. |
| `K_RESULTS` | 5 | Number of results returned. |
| `RRF_K` | 60 | Reciprocal rank fusion constant. |
| `S390X_STOPWORDS` | set | Domain stopwords removed before search. |
| Intent token sets | various | Token sets that trigger intent-based reranking (see below). |
| `DISTRO_TOKENS` | set | Distro keywords that trigger reranking bonus (see below). |

Reranking bonus weights are in `s390x_kb_search/search.py` (`rerank_candidates`):

| Bonus | Weight | Trigger |
|-------|--------|---------|
| Build Guide intent | +0.30 | Query tokens match `BUILD_GUIDE_INTENT_TOKENS` and doc type matches |
| Porting intent | +0.25 | Query tokens match `PORTING_INTENT_TOKENS` (routes to Build Guide) |
| Distro match | +0.15 | Query mentions a distro from `DISTRO_TOKENS` and entry contains it |

After tuning, always re-run `embedding-generation/run_eval.sh` to confirm metrics don't regress.

### Agent Integration Configs

If you change the Docker image name/tag or add new tools, update the MCP configs:

- `agent-integrations/claude-code/.mcp.json`
- `agent-integrations/cursor/mcp.json`
- `agent-integrations/ibm-bob/mcp.json`
- `agent-integrations/vs-code/mcp.json`
- `agent-integrations/windsurf/mcp_config.json`

### Adding Eval Questions

To improve search quality coverage, add entries to `embedding-generation/eval_questions.json`. Each entry should have:
- A natural language question
- One or more expected URLs that should appear in the results

Run `bash embedding-generation/run_eval.sh` to verify the new questions pass.
