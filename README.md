# S390x Linux MCP Server

MCP server for building and porting open-source software on s390x Linux (IBM Z / LinuxONE). Provides knowledge base search across 96+ software packages, build script generation, endian analysis, and container architecture checking.

## Tools

| Tool | Description |
|------|-------------|
| `knowledge_base_search` | Hybrid semantic+keyword search over build guides, porting fixes, and scripts |
| `build_script_generate` | Retrieve build scripts for specific software/version/distro combinations |
| `check_s390x_image` | Check if a Docker image supports the s390x architecture |
| `endian_scan` | Scan source code for endian-specific issues (C/C++, Go, Java, Python) |
| `port_analysis` | Comprehensive porting assessment with portability score and fix recommendations |
| `skopeo` | Container image remote inspection for s390x support |

## Quick Start

### Docker (recommended)

Build the Docker image first:

```bash
# Build the embeddings image
docker build -t s390x-mcp:embeddings-latest -f embedding-generation/Dockerfile .

# Build the MCP server image
docker build -t s390x-mcp:latest -f mcp-server/Dockerfile .
```

Then run the server:

```bash
docker run --rm -i -v $(pwd):/workspace s390x-mcp:latest
```

### Claude Code

Copy `agent-integrations/claude-code/.mcp.json` to your project root, or add to your Claude Code settings:

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

### IBM Bob

Copy `agent-integrations/ibm-bob/mcp.json` to your project's `.bob/` folder, or add to your IBM Bob MCP settings:

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

### Local Development

```bash
pip install -e .
pip install -r mcp-server/requirements.txt
python mcp-server/server.py
```

## Knowledge Sources

- **s390x-oss-kb**: 127 structured fix entries with root causes, fix details, and patch URLs
- **linux-on-ibm-z/docs/wiki**: 117 wiki pages with step-by-step build instructions
- **linux-on-ibm-z/scripts**: 74 packages with version-specific build scripts
- **bob-portgenesis patterns**: Endian detection patterns for C/C++, Go, Java, Python

## Knowledge Base

Pre-built knowledge base artifacts are included in the repo under `mcp-server/data/`. No additional setup is needed to start using the server.

If you want to rebuild the knowledge base (e.g., to incorporate the latest upstream content), run the embedding pipeline:

```bash
# Clone the knowledge source repos
git clone --depth 1 https://github.com/linux-on-ibm-z/docs.wiki.git /tmp/wiki
git clone --depth 1 https://github.com/linux-on-ibm-z/scripts.git /tmp/scripts

# Generate chunks from all sources
python embedding-generation/generate_chunks.py \
  --oss-kb-dir /path/to/s390x-oss-kb \
  --wiki-dir /tmp/wiki \
  --scripts-dir /tmp/scripts \
  --output-dir embedding-generation/output \
  --script-index-output mcp-server/data/script_index.json

# Generate vector store
python embedding-generation/local_vectorstore_creation.py \
  --metadata embedding-generation/output/metadata.json \
  --output-dir mcp-server/data

# Evaluate search quality
bash embedding-generation/run_eval.sh
```

See [docs/MAINTENANCE.md](docs/MAINTENANCE.md) for detailed maintenance and update procedures.

## Architecture

```
Embedding Generation (offline)          MCP Server (runtime)
┌──────────────────────────┐           ┌──────────────────────────────┐
│ s390x-oss-kb (fixes) ─┐  │           │ FastMCP (stdio)              │
│ wiki pages ───────────>│──┤ baked     │ ├── knowledge_base_search    │
│ build scripts ────────>│  │ into      │ ├── build_script_generate    │
│                  chunks│  │ Docker    │ ├── check_s390x_image        │
│                  embed │  ├──────────>│ ├── endian_scan              │
│                  index │  │           │ ├── port_analysis            │
└──────────────────────────┘           │ └── skopeo                   │
                                       └──────────────────────────────┘
```

## Testing

```bash
# Run all tests
python -m pytest mcp-server/tests/ -v

# Run specific test suites
python -m pytest mcp-server/tests/test_endian_scan.py -v
python -m pytest mcp-server/tests/test_port_analysis.py -v
python -m pytest mcp-server/tests/test_docker_utils.py -v
python -m pytest mcp-server/tests/test_kb_search.py -v
```

## License

Apache 2.0
