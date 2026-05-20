from __future__ import annotations

import re

from utils.endian_scan_utils import scan_source_code, detect_language, load_fixes, _normalize_language

GO_ARCH_EXCLUDE_PATTERN = re.compile(
    r'//\s*go:build.*(?:amd64|386|arm64|arm|mips)'
)
GO_OLD_BUILD_TAG = re.compile(
    r'//\s*\+build.*(?:amd64|386|arm64|arm|mips)'
)
_S390X_MENTIONED = re.compile(r'\bs390x\b')
GO_EXCLUDE_S390X = re.compile(r'//\s*(?:go:build|\+build).*!s390x')
CGO_IMPORT = re.compile(r'import\s+"C"')
CGO_CALL = re.compile(r'\bC\.[A-Za-z_][A-Za-z0-9_]*')

PROBLEMATIC_LIBRARIES = [
    ("tpm", "TPM (Trusted Platform Module) - often no s390x support"),
    ("simulator", "Hardware simulator - likely architecture-specific"),
    ("sgx", "Intel SGX - x86-specific security feature"),
    ("avx", "AVX instructions - x86-specific SIMD"),
    ("sse", "SSE instructions - x86-specific SIMD"),
    ("neon", "NEON instructions - ARM-specific SIMD"),
]


def check_arch_compatibility(source_code: str, language: str | None = None) -> dict:
    results: dict = {
        "build_constraints": [],
        "cgo_usage": [],
        "problematic_libraries": [],
        "arch_specific_files": [],
    }

    if language != "Go":
        return results

    for line_num, line in enumerate(source_code.splitlines(), 1):
        if GO_EXCLUDE_S390X.search(line):
            results["build_constraints"].append({
                "line": line_num,
                "constraint": line.strip(),
                "issue": "Explicitly excludes s390x",
                "severity": "CRITICAL",
            })
        elif GO_ARCH_EXCLUDE_PATTERN.search(line) and not _S390X_MENTIONED.search(line):
            results["build_constraints"].append({
                "line": line_num,
                "constraint": line.strip(),
                "issue": "Architecture-specific constraint may exclude s390x",
                "severity": "WARNING",
            })
        elif GO_OLD_BUILD_TAG.search(line) and not _S390X_MENTIONED.search(line):
            results["build_constraints"].append({
                "line": line_num,
                "constraint": line.strip(),
                "issue": "Old-style build tag may exclude s390x",
                "severity": "WARNING",
            })

        if CGO_IMPORT.search(line):
            results["cgo_usage"].append({
                "line": line_num,
                "code": line.strip(),
                "issue": "CGO import - C dependencies must be available on s390x",
            })

        line_lower = line.lower()
        for keyword, description in PROBLEMATIC_LIBRARIES:
            if keyword in line_lower:
                results["problematic_libraries"].append({
                    "line": line_num,
                    "library": keyword,
                    "description": description,
                    "code": line.strip(),
                })

    return results


def calculate_portability_score(endian_results: dict, arch_results: dict) -> int:
    score = 100

    score -= endian_results.get("critical_count", 0) * 15
    score -= endian_results.get("warning_count", 0) * 5

    for constraint in arch_results.get("build_constraints", []):
        if constraint.get("severity") == "CRITICAL":
            score -= 25
        else:
            score -= 10

    score -= len(arch_results.get("cgo_usage", [])) * 5
    score -= len(arch_results.get("problematic_libraries", [])) * 10

    return max(0, min(100, score))


def estimate_porting_effort(endian_results: dict, arch_results: dict) -> str:
    score = calculate_portability_score(endian_results, arch_results)

    if score >= 90:
        return "minimal"
    elif score >= 70:
        return "low"
    elif score >= 50:
        return "moderate"
    elif score >= 30:
        return "significant"
    else:
        return "extensive"


def generate_recommendations(endian_results: dict, arch_results: dict) -> list[str]:
    recommendations = []

    if endian_results.get("critical_count", 0) > 0:
        recommendations.append(
            "Fix critical endian issues before attempting to build on s390x. "
            "These will cause data corruption or crashes on big-endian systems."
        )

    for constraint in arch_results.get("build_constraints", []):
        if constraint.get("severity") == "CRITICAL":
            recommendations.append(
                f"Build constraint at line {constraint['line']} explicitly excludes s390x. "
                "Add s390x to the build constraint or create s390x-specific source files."
            )

    if arch_results.get("cgo_usage"):
        recommendations.append(
            "CGO is used - ensure all C dependencies are available for s390x. "
            "Check that native libraries have s390x builds."
        )

    if arch_results.get("problematic_libraries"):
        libs = [p["library"] for p in arch_results["problematic_libraries"]]
        recommendations.append(
            f"Potentially problematic libraries detected: {', '.join(libs)}. "
            "These may not have s390x support."
        )

    if endian_results.get("warning_count", 0) > 5:
        recommendations.append(
            "Multiple endian warnings detected. Review binary I/O operations "
            "and struct serialization for byte order assumptions."
        )

    if not recommendations:
        recommendations.append(
            "Code appears largely portable to s390x. Run the test suite on an s390x system "
            "to verify runtime behavior."
        )

    return recommendations


def full_port_analysis(
    source_code: str,
    language: str | None = None,
    file_path: str | None = None,
    software_name: str | None = None,
) -> dict:
    language = _normalize_language(language)
    if language is None:
        language = detect_language(file_path, source_code)

    endian_results = scan_source_code(source_code, language=language, file_path=file_path)
    arch_results = check_arch_compatibility(source_code, language=language)

    fixes = load_fixes()
    fix_recommendations = []
    for finding in endian_results.get("findings", []):
        if finding.get("fix_recommendation"):
            fix_recommendations.append({
                "for_finding": finding["description"],
                "at_line": finding["line"],
                **finding["fix_recommendation"],
            })

    score = calculate_portability_score(endian_results, arch_results)
    effort = estimate_porting_effort(endian_results, arch_results)
    recommendations = generate_recommendations(endian_results, arch_results)

    existing_build_guides = None
    if software_name:
        try:
            from utils.kb_search_utils import search_knowledge_base
            existing_build_guides = search_knowledge_base(f"build {software_name} s390x")
        except Exception:
            pass

    return {
        "endian_analysis": endian_results,
        "arch_analysis": arch_results,
        "fix_recommendations": fix_recommendations,
        "existing_build_guides": existing_build_guides,
        "overall_assessment": {
            "portability_score": score,
            "effort_estimate": effort,
            "recommendations": recommendations,
        },
    }
