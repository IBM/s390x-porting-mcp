# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2025-07-27

Initial GA release of the S390x Porting MCP Server.

### Features
- **knowledge_base_search**: Hybrid semantic + keyword search over 136 software packages with build guides and scripts
- **build_script_generate**: Retrieve existing build scripts for 81 packages across RHEL, SLES, and Ubuntu
- **check_s390x_image**: Check Docker Hub images for s390x architecture support
- **endian_scan**: Static analysis for endianness issues in C/C++, Go, Java, and Python
- **port_analysis**: Comprehensive porting assessment with portability score (0-100) and effort estimates
- **skopeo**: Remote container image inspection via skopeo

### Infrastructure
- Pre-built Docker image on Quay.io (`quay.io/ibm/s390x-porting-mcp`)
- Multi-arch builds (amd64 + arm64)
- GitHub Actions CI/CD (lint, test, Docker publish)
- Automated knowledge base update pipeline with quality gates
- Agent integration configs for Claude Code, IBM Bob, Cursor, VS Code, and Windsurf

### Security
- Skopeo transport restricted to docker-only
- Registry host validation (blocks metadata endpoints, link-local addresses)
- Image reference format validation
- Defense-in-depth transport guard

[0.1.0]: https://github.com/IBM/s390x-porting-mcp/releases/tag/v0.1.0
