import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.port_analysis_utils import (
    calculate_portability_score,
    check_arch_compatibility,
    estimate_porting_effort,
    full_port_analysis,
    generate_recommendations,
)


class TestArchCompatibility:
    def test_go_exclude_s390x(self):
        code = "//go:build !s390x\n\npackage main"
        result = check_arch_compatibility(code, language="Go")
        assert len(result["build_constraints"]) >= 1
        assert result["build_constraints"][0]["severity"] == "CRITICAL"

    def test_go_amd64_only(self):
        code = "//go:build amd64\n\npackage main"
        result = check_arch_compatibility(code, language="Go")
        assert len(result["build_constraints"]) >= 1

    def test_go_old_build_tag(self):
        code = "// +build amd64\n\npackage main"
        result = check_arch_compatibility(code, language="Go")
        assert len(result["build_constraints"]) >= 1

    def test_go_cgo_detected(self):
        code = 'package main\n\nimport "C"\n\nfunc main() {}'
        result = check_arch_compatibility(code, language="Go")
        assert len(result["cgo_usage"]) >= 1

    def test_go_problematic_library(self):
        code = 'package main\n\nimport "github.com/google/go-tpm/tpm2"'
        result = check_arch_compatibility(code, language="Go")
        assert len(result["problematic_libraries"]) >= 1

    def test_non_go_returns_empty(self):
        code = "#include <stdio.h>\nint main() { return 0; }"
        result = check_arch_compatibility(code, language="C")
        assert result["build_constraints"] == []
        assert result["cgo_usage"] == []

    def test_go_with_s390x_included(self):
        code = "//go:build amd64 || s390x\n\npackage main"
        result = check_arch_compatibility(code, language="Go")
        constraints_excluding = [c for c in result["build_constraints"] if "exclude" in c.get("issue", "").lower()]
        assert len(constraints_excluding) == 0


class TestPortabilityScore:
    def test_perfect_score(self):
        endian = {"critical_count": 0, "warning_count": 0}
        arch = {"build_constraints": [], "cgo_usage": [], "problematic_libraries": []}
        assert calculate_portability_score(endian, arch) == 100

    def test_critical_endian_reduces_score(self):
        endian = {"critical_count": 3, "warning_count": 0}
        arch = {"build_constraints": [], "cgo_usage": [], "problematic_libraries": []}
        assert calculate_portability_score(endian, arch) == 55

    def test_arch_exclusion_reduces_score(self):
        endian = {"critical_count": 0, "warning_count": 0}
        arch = {
            "build_constraints": [{"severity": "CRITICAL"}],
            "cgo_usage": [],
            "problematic_libraries": [],
        }
        assert calculate_portability_score(endian, arch) == 75

    def test_floor_at_zero(self):
        endian = {"critical_count": 10, "warning_count": 20}
        arch = {
            "build_constraints": [{"severity": "CRITICAL"}] * 5,
            "cgo_usage": [{}] * 10,
            "problematic_libraries": [{}] * 5,
        }
        assert calculate_portability_score(endian, arch) == 0


class TestEffortEstimate:
    def test_minimal_effort(self):
        endian = {"critical_count": 0, "warning_count": 0}
        arch = {"build_constraints": [], "cgo_usage": [], "problematic_libraries": []}
        assert estimate_porting_effort(endian, arch) == "minimal"

    def test_extensive_effort(self):
        endian = {"critical_count": 10, "warning_count": 10}
        arch = {
            "build_constraints": [{"severity": "CRITICAL"}] * 3,
            "cgo_usage": [],
            "problematic_libraries": [],
        }
        assert estimate_porting_effort(endian, arch) == "extensive"


class TestRecommendations:
    def test_no_issues_recommendation(self):
        endian = {"critical_count": 0, "warning_count": 0, "findings": []}
        arch = {"build_constraints": [], "cgo_usage": [], "problematic_libraries": []}
        recs = generate_recommendations(endian, arch)
        assert len(recs) >= 1
        assert "portable" in recs[0].lower() or "test" in recs[0].lower()

    def test_critical_endian_recommendation(self):
        endian = {"critical_count": 2, "warning_count": 0, "findings": []}
        arch = {"build_constraints": [], "cgo_usage": [], "problematic_libraries": []}
        recs = generate_recommendations(endian, arch)
        assert any("critical" in r.lower() for r in recs)


class TestFullPortAnalysis:
    def test_c_code_with_issues(self):
        code = """
#include <endian.h>
uint32_t convert(uint32_t val) {
    return htole32(val);
}
"""
        result = full_port_analysis(code, language="C")
        assert "endian_analysis" in result
        assert "arch_analysis" in result
        assert "overall_assessment" in result
        assert result["endian_analysis"]["critical_count"] >= 1
        assert result["overall_assessment"]["portability_score"] < 100

    def test_go_code_with_arch_issue(self):
        code = "//go:build !s390x\n\npackage main\n\nfunc main() {}"
        result = full_port_analysis(code, language="Go")
        assert len(result["arch_analysis"]["build_constraints"]) >= 1
        assert result["overall_assessment"]["portability_score"] < 100

    def test_clean_code(self):
        code = 'package main\n\nimport "fmt"\n\nfunc main() {\n    fmt.Println("hello")\n}'
        result = full_port_analysis(code, language="Go")
        assert result["overall_assessment"]["portability_score"] >= 90
        assert result["overall_assessment"]["effort_estimate"] == "minimal"
