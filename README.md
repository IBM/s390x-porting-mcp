# S390x Linux MCP Server

MCP server for building and porting open-source software on s390x Linux (IBM Z / LinuxONE). Provides knowledge base search across 96+ software packages, build script generation, endian analysis, and container architecture checking.

## Tools

| Tool | Description |
|------|-------------|
| `knowledge_base_search` | Hybrid semantic+keyword search over build guides and scripts |
| `build_script_generate` | Retrieve build scripts for specific software/version/distro combinations |
| `check_s390x_image` | Check if a Docker image supports the s390x architecture |
| `endian_scan` | Scan source code for endian-specific issues (C/C++, Go, Java, Python) |
| `port_analysis` | Comprehensive porting assessment with portability score and fix recommendations |
| `skopeo` | Container image remote inspection for s390x support |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) or [Podman](https://podman.io/)

## Quick Start

Add the MCP server to your AI coding agent. The Docker image (`quay.io/ibm/s390x-porting-mcp:latest`) is pulled automatically on first use.

### Claude Code

Copy `agent-integrations/claude-code/.mcp.json` to your project root, or add to your Claude Code settings:

```json
{
  "mcpServers": {
    "s390x": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "-v", "${workspaceFolder}:/workspace", "quay.io/ibm/s390x-porting-mcp:latest"]
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
      "args": ["run", "--rm", "-i", "-v", "${workspaceFolder}:/workspace", "quay.io/ibm/s390x-porting-mcp:latest"]
    }
  }
}
```

### Cursor

Copy `agent-integrations/cursor/mcp.json` to your project's `.cursor/` folder, or add to your Cursor MCP settings:

```json
{
  "mcpServers": {
    "s390x": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "-v", "${workspaceFolder}:/workspace", "quay.io/ibm/s390x-porting-mcp:latest"]
    }
  }
}
```

### VS Code

Copy `agent-integrations/vs-code/mcp.json` to your project's `.vscode/` folder, or add to your VS Code MCP settings:

```json
{
  "mcpServers": {
    "s390x": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "-v", "${workspaceFolder}:/workspace", "quay.io/ibm/s390x-porting-mcp:latest"]
    }
  }
}
```

### Windsurf

Copy `agent-integrations/windsurf/mcp_config.json` to your Windsurf config, or add to your MCP settings:

```json
{
  "mcpServers": {
    "s390x": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "-v", "${workspaceFolder}:/workspace", "quay.io/ibm/s390x-porting-mcp:latest"]
    }
  }
}
```

## Knowledge Sources

Embedded in the vector store (searched by `knowledge_base_search`):

- **linux-on-ibm-z/docs/wiki**: 117 wiki pages with step-by-step build instructions
- **linux-on-ibm-z/scripts**: 74 packages with version-specific build scripts

Runtime patterns (loaded directly by `endian_scan` and `port_analysis`):

- **mcp-server/patterns/**: Endian detection patterns for C/C++, Go, Java, Python (derived from bob-portgenesis)

## Architecture

```
Embedding Generation (offline)          MCP Server (runtime)
┌──────────────────────────┐           ┌──────────────────────────────┐
│ wiki pages ───────────┐  │           │ FastMCP (stdio)              │
│ build scripts ────────>──┤ baked     │ ├── knowledge_base_search    │
│                  chunks│  │ into      │ ├── build_script_generate    │
│                  embed │  │ Docker    │ ├── check_s390x_image        │
│                  index │  ├──────────>│ ├── endian_scan              │
│                        │  │           │ ├── port_analysis            │
└──────────────────────────┘           │ └── skopeo                   │
                                       └──────────────────────────────┘
```

## Building from Source

If you want to build the Docker image locally instead of pulling from Quay.io:

```bash
# Build the embeddings image
docker build -t s390x-mcp:embeddings-latest -f embedding-generation/Dockerfile .

# Build the MCP server image
docker build -t s390x-mcp:latest -f mcp-server/Dockerfile .
```

The embeddings image must be built first — the server Dockerfile copies artifacts from it.

### Local Development

```bash
pip install -e .
pip install -r mcp-server/requirements.txt
python mcp-server/server.py
```

## Knowledge Base

Pre-built knowledge base artifacts are included in the repo under `mcp-server/data/`. No additional setup is needed to start using the server.

If you want to rebuild the knowledge base (e.g., to incorporate the latest upstream content), run the embedding pipeline:

```bash
# Clone the knowledge source repos
git clone --depth 1 https://github.com/linux-on-ibm-z/docs.wiki.git /tmp/wiki
git clone --depth 1 https://github.com/linux-on-ibm-z/scripts.git /tmp/scripts

# Generate chunks from all sources
python embedding-generation/generate_chunks.py \
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
