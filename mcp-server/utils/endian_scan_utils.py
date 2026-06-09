from __future__ import annotations

import os
import re
from dataclasses import dataclass

from utils.config import PATTERNS_DIR

EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cxx": "C++",
    ".cc": "C++",
    ".hpp": "C++",
    ".hxx": "C++",
    ".go": "Go",
    ".java": "Java",
    ".py": "Python",
}

_LANGUAGE_ALIASES: dict[str, str] = {
    "c": "C",
    "c++": "C++",
    "cpp": "C++",
    "cxx": "C++",
    "go": "Go",
    "golang": "Go",
    "java": "Java",
    "python": "Python",
    "py": "Python",
}


def _normalize_language(language: str | None) -> str | None:
    if language is None:
        return None
    return _LANGUAGE_ALIASES.get(language.lower(), language)

PATTERN_FILES: dict[str, str] = {
    "common": "endian-patterns.txt",
    "C": "c-cpp-patterns.txt",
    "C++": "c-cpp-patterns.txt",
    "Go": "go-patterns.txt",
    "Java": "java-patterns.txt",
    "Python": "python-patterns.txt",
}


@dataclass
class Pattern:
    severity: str
    regex: re.Pattern[str]
    description: str
    languages: set[str]
    raw_pattern: str


@dataclass
class FixRecommendation:
    pattern_id: str
    fix_description: str
    code_before: str
    code_after: str
    explanation: str


_pattern_cache: dict[str, list[Pattern]] = {}
_fix_cache: list[FixRecommendation] = []


def _parse_languages(lang_str: str) -> set[str]:
    if not lang_str or lang_str.strip() == "ALL":
        return {"ALL"}
    return {l.strip() for l in lang_str.split(",")}


def _load_pattern_file(filepath: str) -> list[Pattern]:
    patterns = []
    if not os.path.exists(filepath):
        return patterns

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            if len(parts) < 3:
                continue

            severity = parts[0].strip()
            raw_pattern = parts[1].strip()
            description = parts[2].strip()
            languages = _parse_languages(parts[3].strip()) if len(parts) > 3 else {"ALL"}

            try:
                compiled = re.compile(raw_pattern)
            except re.error:
                continue

            patterns.append(Pattern(
                severity=severity,
                regex=compiled,
                description=description,
                languages=languages,
                raw_pattern=raw_pattern,
            ))

    return patterns


def load_patterns(language: str | None = None) -> list[Pattern]:
    cache_key = language or "ALL"
    if cache_key in _pattern_cache:
        return _pattern_cache[cache_key]

    common_path = os.path.join(PATTERNS_DIR, PATTERN_FILES["common"])
    all_patterns = _load_pattern_file(common_path)

    if language and language in PATTERN_FILES:
        lang_path = os.path.join(PATTERNS_DIR, PATTERN_FILES[language])
        if lang_path != common_path:
            all_patterns.extend(_load_pattern_file(lang_path))

    if language:
        filtered = [
            p for p in all_patterns
            if "ALL" in p.languages or language in p.languages
        ]
    else:
        filtered = all_patterns

    _pattern_cache[cache_key] = filtered
    return filtered


def load_fixes() -> list[FixRecommendation]:
    global _fix_cache
    if _fix_cache:
        return _fix_cache

    fixes_path = os.path.join(PATTERNS_DIR, "endian-fixes.txt")
    if not os.path.exists(fixes_path):
        return []

    fixes = []
    with open(fixes_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            if len(parts) < 5:
                continue

            fixes.append(FixRecommendation(
                pattern_id=parts[0].strip(),
                fix_description=parts[1].strip(),
                code_before=parts[2].strip().replace("\\n", "\n"),
                code_after=parts[3].strip().replace("\\n", "\n"),
                explanation=parts[4].strip(),
            ))

    _fix_cache = fixes
    return fixes


def get_fix_recommendation(raw_pattern: str) -> FixRecommendation | None:
    fixes = load_fixes()
    for fix in fixes:
        try:
            if re.search(re.escape(fix.pattern_id), raw_pattern):
                return fix
        except re.error:
            if fix.pattern_id in raw_pattern:
                return fix
    return None


def detect_language(file_path: str | None = None, source_code: str | None = None) -> str | None:
    if file_path:
        _, ext = os.path.splitext(file_path)
        if ext in EXTENSION_TO_LANGUAGE:
            return EXTENSION_TO_LANGUAGE[ext]

    if source_code:
        indicators = {
            "Go": [r'\bpackage\s+\w+', r'\bfunc\s+\w+', r'\bimport\s+"'],
            "Python": [r'\bdef\s+\w+', r'\bimport\s+\w+', r'\bclass\s+\w+.*:'],
            "Java": [r'\bpublic\s+class\b', r'\bimport\s+java\.', r'\bprivate\s+\w+\s+\w+\s*\('],
            "C++": [r'#include\s+<\w+>', r'\bstd::', r'\bnamespace\s+\w+', r'\btemplate\s*<'],
            "C": [r'#include\s+<\w+\.h>', r'\bvoid\s+\w+\s*\(', r'\btypedef\s+struct'],
        }
        scores: dict[str, int] = {}
        for lang, pats in indicators.items():
            scores[lang] = sum(1 for p in pats if re.search(p, source_code))

        if scores:
            best = max(scores, key=lambda k: scores[k])
            if scores[best] > 0:
                return best

    return None


def scan_source_code(
    source_code: str,
    language: str | None = None,
    file_path: str | None = None,
) -> dict:
    language = _normalize_language(language)
    if language is None:
        language = detect_language(file_path, source_code)

    detected_language = language or "unknown"
    patterns = load_patterns(language)
    lines = source_code.splitlines()
    findings: list[dict] = []
    seen: set[tuple[int, str]] = set()

    for line_num, line in enumerate(lines, 1):
        for pattern in patterns:
            if pattern.regex.search(line):
                key = (line_num, pattern.raw_pattern)
                if key in seen:
                    continue
                seen.add(key)

                fix = get_fix_recommendation(pattern.raw_pattern)
                finding: dict = {
                    "line": line_num,
                    "severity": pattern.severity,
                    "description": pattern.description,
                    "matched_code": line.strip(),
                }
                if fix:
                    finding["fix_recommendation"] = {
                        "fix_description": fix.fix_description,
                        "code_before": fix.code_before,
                        "code_after": fix.code_after,
                        "explanation": fix.explanation,
                    }
                findings.append(finding)

    critical = sum(1 for f in findings if f["severity"] == "CRITICAL")
    warning = sum(1 for f in findings if f["severity"] == "WARNING")
    info = sum(1 for f in findings if f["severity"] == "INFO")

    if critical > 0:
        status = "REQUIRES CHANGES"
    elif warning > 5:
        status = "REVIEW RECOMMENDED"
    elif warning > 0:
        status = "REVIEW SUGGESTED"
    else:
        status = "ENDIAN-NEUTRAL"

    return {
        "overall_status": status,
        "critical_count": critical,
        "warning_count": warning,
        "info_count": info,
        "findings": findings,
        "language": detected_language,
        "total_lines": len(lines),
    }
