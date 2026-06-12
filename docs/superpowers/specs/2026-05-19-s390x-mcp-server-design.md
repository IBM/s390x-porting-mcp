# S390x Linux MCP Server Design Spec

## Context

No MCP server exists for IBM Z / s390x Linux. Developers and operations teams porting or building open-source software on IBM Z must manually search across scattered wikis, scripts, and internal tools. The ARM MCP server (github.com/arm/mcp) demonstrates a proven pattern for an architecture-specific MCP server. This project creates an equivalent for s390x, combining knowledge base search with porting analysis tools.

## Knowledge Sources

Two sources are merged into a unified knowledge base:

1. **linux-on-ibm-z/docs/wiki**: 117 wiki pages with step-by-step build instructions per software package. Multi-version, multi-distro (RHEL, SLES, Ubuntu). URL pattern: `github.com/linux-on-ibm-z/docs/wiki/Building-[Name]`

2. **linux-on-ibm-z/scripts**: 74 directories with version-specific shell build scripts. Pattern: `{package}/{version}/build_{package}.sh`

Pattern databases from **bob-portgenesis** (github.ibm.com/rishi/bob-portgenesis) are vendored for the endian scanning tools: 6 language-specific pattern files + 56-entry fix recommendations database.

## Architecture Overview

```
                     EMBEDDING GENERATION (offline)
  ┌────────────────────────────────────────────────────────────┐
  │  wiki pages ────┐── chunk ── embed ── metadata.json        │
  │  build scripts ─┘                      usearch_index.bin   │
  └────────────────────────────────────────────────────────────┘
                              │ baked into Docker image
                              v
                      MCP SERVER (runtime)
  ┌────────────────────────────────────────────────────────────┐
  │  FastMCP (stdio transport)                                 │
  │  ├── knowledge_base_search  (hybrid: USearch + BM25 + RRF)│
  │  ├── build_script_generate  (index lookup + KB fallback)   │
  │  ├── check_s390x_image      (Docker registry API)          │
  │  ├── endian_scan            (Python regex, pattern DBs)    │
  │  ├── port_analysis          (endian + arch + fixes + KB)   │
  │  └── skopeo                 (container inspection)         │
  └────────────────────────────────────────────────────────────┘
```

## Project Structure

```
s390x-mcp/
├── pyproject.toml                          # s390x-kb-search library
├── README.md
├── LICENSE                                 # Apache 2.0
├── s390x_kb_search/                        # Standalone search library
│   ├── __init__.py                         # Public API: load_search_resources, search
│   ├── config.py                           # DISTANCE_THRESHOLD, K_RESULTS
│   ├── loaders.py                          # load_metadata, load_usearch_index
│   ├── resources.py                        # SearchResources dataclass
│   ├── search.py                           # hybrid_search, bm25_search, embedding_search, reranking
│   ├── response.py                         # Content disclaimers
│   └── evaluation.py                       # Hit@K, MRR evaluation
├── embedding-generation/                   # Offline pipeline
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── s390x-kb-sources.csv                # Source manifest
│   ├── fetch_wiki_pages.py                 # Clone docs.wiki.git, read markdown
│   ├── fetch_build_scripts.py              # Clone scripts repo, read shell files
│   ├── generate_chunks.py                  # Orchestrator: fetch -> parse -> chunk
│   ├── local_vectorstore_creation.py       # SentenceTransformer + USearch index
│   ├── eval_questions.json                 # Test questions with expected URLs
│   └── run_eval.sh                         # End-to-end eval script
├── mcp-server/
│   ├── server.py                           # FastMCP server, 6 @mcp.tool definitions
│   ├── server.json                         # MCP server metadata
│   ├── requirements.txt
│   ├── Dockerfile                          # Multi-stage build
│   ├── data/                               # Pre-built artifacts (generated)
│   │   ├── metadata.json
│   │   ├── usearch_index.bin
│   │   └── script_index.json              # Package -> script path mapping
│   ├── patterns/                           # Vendored from bob-portgenesis
│   │   ├── endian-patterns.txt
│   │   ├── c-cpp-patterns.txt
│   │   ├── go-patterns.txt
│   │   ├── java-patterns.txt
│   │   ├── python-patterns.txt
│   │   └── endian-fixes.txt
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config.py                       # Centralized paths and constants
│   │   ├── error_handling.py               # format_tool_error()
│   │   ├── invocation_logger.py            # log_invocation_reason()
│   │   ├── cli_utils.py                    # run_command() subprocess wrapper
│   │   ├── kb_search_utils.py              # Knowledge base search helper
│   │   ├── build_script_utils.py           # Script lookup + metadata extraction
│   │   ├── docker_utils.py                 # Docker registry API for arch checking
│   │   ├── skopeo_tool.py                  # Skopeo container inspection
│   │   ├── endian_scan_utils.py            # Python port of pattern matching
│   │   └── port_analysis_utils.py          # Full porting assessment
│   └── tests/
│       ├── test_kb_search.py
│       ├── test_endian_scan.py
│       ├── test_port_analysis.py
│       ├── test_build_script.py
│       ├── test_docker_utils.py
│       └── test_mcp.py                     # Integration tests
├── agent-integrations/
│   ├── claude-code/
│   ├── cursor/
│   ├── vs-code/
│   └── windsurf/
└── .github/workflows/
    ├── ci.yml
    ├── embeddings.yml
    └── docker-publish.yml
```

## Tool Specifications

### 1. knowledge_base_search

Search across all embedded content: wiki build guides and build scripts.

**Inputs:**
- `query: str` -- Natural language search query
- `invocation_reason: Optional[str]` -- Why the model is calling this tool

**Outputs:** List of ranked results, each with: `url`, `title`, `heading`, `snippet`, `doc_type` (Build Guide | Build Script), `product`, `distance`, `score`

**Search pipeline** (follows ARM's implementation):
1. Dense search: encode query with SentenceTransformer(`all-MiniLM-L6-v2`), search USearch index (384-dim, L2sq metric)
2. Sparse search: BM25Okapi keyword matching
3. Reciprocal Rank Fusion (RRF_K=60) to merge results
4. Reranking with s390x-specific signals:
   - Text/title/heading overlap bonuses
   - doc_type boost based on query intent (build/porting intent -> Build Guide +0.30, script intent -> Build Script +0.25)
   - Distro match bonus (+0.15 when query mentions specific distro)
   - Version recency bonus (+0.10 for matching version)

### 2. build_script_generate

Look up existing build scripts by software name, version, and target distro.

**Inputs:**
- `software: str` -- Package name (e.g., "Grafana", "PostgreSQL")
- `version: Optional[str]` -- Target version
- `distro: Optional[str]` -- Target distro (ubuntu, rhel, sles)
- `invocation_reason: Optional[str]`

**Outputs:** Dict with `status`, `script_content` or `script_url`, `package`, `version`, `distro`, `source`

**Implementation:**
1. Look up `script_index.json` (pre-built mapping of normalized package names -> version dirs -> script paths)
2. If exact match found, return script content + metadata
3. If no exact match, fall back to KB search for build instructions
4. Extract metadata from script: dependencies per distro, build commands, test commands

### 3. check_s390x_image

Check if a Docker image has s390x architecture support via Docker Hub registry API.

**Inputs:**
- `image: str` -- Image in "name:tag" format
- `invocation_reason: Optional[str]`

**Outputs:** Dict with `status`, `architectures` (list), `s390x_supported` (bool), `message`

**Implementation:** Docker Hub V2 API calls:
1. Get auth token from `auth.docker.io`
2. Get manifest list from `registry-1.docker.io`
3. Parse platform entries, check for `s390x` in architecture field

### 4. endian_scan

Scan source code for endian-specific issues using vendored pattern databases.

**Inputs:**
- `source_code: str` -- Source code to scan (inline)
- `language: Optional[str]` -- Language hint (auto-detected from file_path or content)
- `file_path: Optional[str]` -- File path hint for language detection
- `invocation_reason: Optional[str]`

**Outputs:** Dict with:
- `overall_status`: "REQUIRES CHANGES" | "REVIEW RECOMMENDED" | "ENDIAN-NEUTRAL"
- `critical_count`, `warning_count`, `info_count`
- `findings`: list of `{line, severity, description, matched_code, fix_recommendation}`
- `language`: detected language

**Implementation:** Pure Python port of bob-portgenesis `endian-scanner.sh`:
- Load patterns from `patterns/*.txt` at startup, compile to regex
- Match each line of source code against applicable patterns
- For each match, look up fix recommendation from `endian-fixes.txt`
- Patterns are cached as module-level compiled regex objects

### 5. port_analysis

Comprehensive porting assessment combining endian scan, architecture compatibility, fix recommendations, and existing build guide lookup.

**Inputs:**
- `source_code: str` -- Source code to analyze
- `language: Optional[str]`
- `file_path: Optional[str]`
- `software_name: Optional[str]` -- For KB lookup of existing guides
- `invocation_reason: Optional[str]`

**Outputs:** Dict with:
- `endian_analysis`: endian scan results
- `arch_analysis`: architecture compatibility (Go build tags, CGO, problematic libraries)
- `fix_recommendations`: actionable fixes with before/after code
- `existing_build_guides`: KB search results if software_name provided
- `overall_assessment`: portability score, effort estimate, recommendations

### 6. skopeo

Container image remote inspection without pulling.

**Inputs:**
- `image: Optional[str]` -- Container image
- `transport: str = "docker"` -- Transport type
- `raw: bool = False` -- Return raw manifest
- `invocation_reason: Optional[str]`

**Outputs:** Dict with `status`, `stdout`, `stderr`, `cmd`

**Implementation:** Subprocess call to `skopeo inspect` (installed in Docker image).

## Embedding Pipeline

### Data Ingestion

Two loaders produce a unified chunk format:

1. **`fetch_wiki_pages.py`**: Shallow-clone `linux-on-ibm-z/docs.wiki.git`, read each `.md` file. Section-aware chunking preserves distro-specific code blocks with their surrounding context.

2. **`fetch_build_scripts.py`**: Shallow-clone `linux-on-ibm-z/scripts`, walk `{package}/{version}/build_*.sh`. Chunk by function (prepare, configureAndInstall, runTest). Extract metadata: package name, version, supported distros.

### Chunk Schema

```json
{
  "uuid": "unique-id",
  "chunk_uuid": "wiki_building-apache-cassandra_section3",
  "url": "https://github.com/linux-on-ibm-z/docs/wiki/Building-Apache-Cassandra",
  "original_text": "...",
  "title": "Building Apache Cassandra",
  "heading": "Step 3 - Build and install",
  "heading_path": ["Apache Cassandra", "Step 3"],
  "doc_type": "Build Guide",
  "product": "Apache Cassandra",
  "version": "5.0.6",
  "distros": ["RHEL 8.10", "Ubuntu 24.04"],
  "keywords": "cassandra build s390x",
  "search_text": "..."
}
```

### Embedding & Indexing

- Model: `all-MiniLM-L6-v2` (384-dim, same as ARM)
- Index: USearch with L2sq metric, connectivity=16, expansion_add=128, expansion_search=64
- Outputs: `metadata.json` (chunk metadata array) + `usearch_index.bin` (vector index)
- Estimated chunk count: ~14,600 (117 wiki pages x ~10 sections + 74 scripts x ~10 versions x ~10 functions)

## Configuration

`mcp-server/utils/config.py`:

| Setting | Value | Purpose |
|---------|-------|---------|
| `MODEL_NAME` | `all-MiniLM-L6-v2` | Embedding model |
| `DISTANCE_THRESHOLD` | 1.1 | Max L2 distance for semantic results |
| `K_RESULTS` | 5 | Default number of results |
| `TARGET_ARCHITECTURES` | `{amd64, s390x}` | Architectures to check for |
| `PATTERNS_DIR` | `../patterns` | Pattern database directory |
| `DATA_DIR` | `../data` | Knowledge base artifacts |

Environment variables: `WORKSPACE_DIR` (/workspace), `S390X_KB_DATA_DIR`, `SENTENCE_TRANSFORMERS_HOME`, `LOG_LEVEL`

## Packaging & Deployment

### Docker (primary)

Multi-stage Dockerfile:
- Stage 0: Pre-built embeddings image
- Stage 1: Builder (Ubuntu 24.04, Python 3, skopeo, pip deps, model cache)
- Stage 2: Runtime (slim, copies venv + data + patterns from builder)
- Entry: `python -u server.py` with stdio transport

### pip install (alternative)

```bash
pip install s390x-mcp
s390x-mcp serve  # starts stdio server
```

Requires user to download data artifacts separately or on first run.

### Client Configs

Provided for Claude Code, Cursor, VS Code, Windsurf in `agent-integrations/`.

Example (Claude Code `.mcp.json`):
```json
{
  "mcpServers": {
    "s390x": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "-v", "${workspaceFolder}:/workspace", "s390x-mcp:latest"]
    }
  }
}
```

## Testing Strategy

### Unit Tests
- `test_endian_scan.py`: Pattern matching against known code samples (positive + negative), severity classification, fix recommendation lookup, language auto-detection
- `test_build_script.py`: Fuzzy package name matching, version resolution, metadata extraction
- `test_docker_utils.py`: Registry API interaction (mocked), s390x detection in manifests
- `test_kb_search.py`: Known queries return expected results, BM25 tokenization, reranking logic

### Integration Tests
- `test_mcp.py`: Start Docker container, send MCP requests via stdio, verify tool responses

### Search Quality Evaluation
- `eval_questions.json`: Test questions with expected URLs
- Metrics: Hit@1 >= 0.60, Hit@3 >= 0.80, MRR >= 0.70
- Run via `embedding-generation/run_eval.sh`

## Verification Plan

1. **Build & run locally**: `pip install -e . && python mcp-server/server.py` — verify server starts, responds to MCP init
2. **Test each tool**:
   - `knowledge_base_search("build grafana on s390x")` — returns Grafana wiki page
   - `build_script_generate("PostgreSQL", "18.3", "ubuntu")` — returns script content
   - `check_s390x_image("nginx:latest")` — returns architecture list with s390x status
   - `endian_scan("uint32_t val = htole32(x);", "C")` — returns CRITICAL finding
   - `port_analysis(go_code, "Go")` — returns combined assessment
   - `skopeo("nginx:latest")` — returns inspection output
3. **Docker build**: `docker build -t s390x-mcp:test -f mcp-server/Dockerfile .` — verify image builds
4. **Docker run**: `docker run --rm -i s390x-mcp:test` — verify MCP protocol works via stdio
5. **Integration test suite**: `pytest mcp-server/tests/ -v`
6. **Search eval**: `bash embedding-generation/run_eval.sh` — verify Hit@1/Hit@3/MRR thresholds
