import logging
import sys
from typing import Optional

from fastmcp import FastMCP
from utils.config import KB_PACKAGE_COUNT, LOG_LEVEL, SCRIPT_PACKAGE_COUNT
from utils.error_handling import format_tool_error
from utils.invocation_logger import log_invocation_reason

logging.basicConfig(level=getattr(logging, LOG_LEVEL), stream=sys.stderr)
logger = logging.getLogger(__name__)

mcp = FastMCP("s390x-mcp")


@mcp.tool(
    description=(
        "IMPORTANT: IF A USER ASKS ABOUT BUILDING OR PORTING SOFTWARE TO S390X/IBM Z, "
        "STRONGLY CONSIDER USING THIS TOOL. Searches a knowledge base of build guides "
        "and scripts for open-source software on s390x Linux (IBM Z). "
        "Given a natural language query, returns matching build instructions "
        f"and scripts ranked by relevance. Covers {KB_PACKAGE_COUNT}+ software packages with multi-distro "
        "(RHEL, SLES, Ubuntu) build steps."
    )
)
def knowledge_base_search(
    query: str,
    invocation_reason: Optional[str] = None,
) -> list[dict] | dict:
    log_invocation_reason(tool="knowledge_base_search", reason=invocation_reason, args={"query": query})
    try:
        from utils.kb_search_utils import search_knowledge_base

        return search_knowledge_base(query)
    except Exception as e:
        return format_tool_error(tool="knowledge_base_search", exc=e, args={"query": query})


@mcp.tool(
    description=(
        "Retrieve an existing build script for software already ported to s390x Linux. "
        f"Searches the linux-on-ibm-z/scripts repository index, covering {SCRIPT_PACKAGE_COUNT}+ software "
        "packages with version-specific build scripts for RHEL, SLES, and Ubuntu. "
        "For packages not yet ported, suggests porting analysis and how to request help."
    )
)
def build_script_generate(
    software: str,
    version: Optional[str] = None,
    distro: Optional[str] = None,
    invocation_reason: Optional[str] = None,
) -> dict:
    log_invocation_reason(
        tool="build_script_generate",
        reason=invocation_reason,
        args={"software": software, "version": version, "distro": distro},
    )
    try:
        from utils.build_script_utils import find_and_return_script

        return find_and_return_script(software, version, distro)
    except Exception as e:
        return format_tool_error(
            tool="build_script_generate", exc=e, args={"software": software, "version": version, "distro": distro}
        )


@mcp.tool(
    description=(
        "Check if a Docker container image supports the s390x architecture. "
        "Queries the Docker Hub registry API to inspect the image manifest "
        "and reports which architectures are available."
    )
)
def check_s390x_image(
    image: str,
    invocation_reason: Optional[str] = None,
) -> dict:
    log_invocation_reason(tool="check_s390x_image", reason=invocation_reason, args={"image": image})
    try:
        from utils.docker_utils import check_docker_image_architectures

        return check_docker_image_architectures(image)
    except Exception as e:
        return format_tool_error(tool="check_s390x_image", exc=e, args={"image": image})


@mcp.tool(
    description=(
        "Scan source code for endian-specific issues that would cause problems on s390x "
        "(big-endian). Detects little-endian assumptions, unsafe casts, bit field issues, "
        "and other architecture-dependent patterns in C/C++, Go, Java, and Python code. "
        "Returns findings with severity levels and fix recommendations."
    )
)
def endian_scan(
    source_code: str,
    language: Optional[str] = None,
    file_path: Optional[str] = None,
    invocation_reason: Optional[str] = None,
) -> dict:
    log_invocation_reason(
        tool="endian_scan",
        reason=invocation_reason,
        args={"language": language, "file_path": file_path, "code_length": len(source_code)},
    )
    try:
        from utils.endian_scan_utils import scan_source_code

        return scan_source_code(source_code, language=language, file_path=file_path)
    except Exception as e:
        return format_tool_error(tool="endian_scan", exc=e, args={"language": language})


@mcp.tool(
    description=(
        "Perform a comprehensive porting analysis for s390x. Combines endian scanning, "
        "architecture compatibility checking (Go build tags, CGO, problematic libraries), "
        "and fix recommendations into a single assessment with a portability score and "
        "effort estimate. Optionally searches the knowledge base for existing build guides."
    )
)
def port_analysis(
    source_code: str,
    language: Optional[str] = None,
    file_path: Optional[str] = None,
    software_name: Optional[str] = None,
    invocation_reason: Optional[str] = None,
) -> dict:
    log_invocation_reason(
        tool="port_analysis",
        reason=invocation_reason,
        args={"language": language, "software_name": software_name, "code_length": len(source_code)},
    )
    try:
        from utils.port_analysis_utils import full_port_analysis

        return full_port_analysis(source_code, language=language, file_path=file_path, software_name=software_name)
    except Exception as e:
        return format_tool_error(tool="port_analysis", exc=e, args={"language": language})


@mcp.tool(
    description=(
        "Inspect a container image remotely without pulling it, using skopeo. "
        "Useful for checking s390x architecture support and image metadata."
    )
)
def skopeo(
    image: Optional[str] = None,
    transport: str = "docker",
    raw: bool = False,
    invocation_reason: Optional[str] = None,
) -> dict:
    log_invocation_reason(tool="skopeo", reason=invocation_reason, args={"image": image})
    try:
        from utils.skopeo_tool import skopeo_inspect

        if image is None:
            from utils.skopeo_tool import skopeo_help

            return skopeo_help()
        return skopeo_inspect(image, transport=transport, raw=raw)
    except Exception as e:
        return format_tool_error(tool="skopeo", exc=e, args={"image": image})


if __name__ == "__main__":
    mcp.run(transport="stdio")
