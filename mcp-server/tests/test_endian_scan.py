import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.endian_scan_utils import (
    detect_language,
    load_fixes,
    load_patterns,
    scan_source_code,
)


class TestDetectLanguage:
    def test_c_extension(self):
        assert detect_language(file_path="main.c") == "C"

    def test_cpp_extension(self):
        assert detect_language(file_path="main.cpp") == "C++"

    def test_go_extension(self):
        assert detect_language(file_path="main.go") == "Go"

    def test_java_extension(self):
        assert detect_language(file_path="Main.java") == "Java"

    def test_python_extension(self):
        assert detect_language(file_path="script.py") == "Python"

    def test_header_extension(self):
        assert detect_language(file_path="header.h") == "C"

    def test_detect_from_content_go(self):
        code = 'package main\n\nimport "fmt"\n\nfunc main() {\n    fmt.Println("hello")\n}'
        assert detect_language(source_code=code) == "Go"

    def test_detect_from_content_python(self):
        code = "def main():\n    import os\n    print('hello')"
        assert detect_language(source_code=code) == "Python"

    def test_unknown(self):
        assert detect_language(source_code="hello world") is None


class TestLoadPatterns:
    def test_loads_common_patterns(self):
        patterns = load_patterns()
        assert len(patterns) > 0

    def test_loads_c_patterns(self):
        patterns = load_patterns("C")
        assert len(patterns) > 0
        descriptions = [p.description for p in patterns]
        assert any("byte" in d.lower() or "endian" in d.lower() for d in descriptions)

    def test_loads_go_patterns(self):
        patterns = load_patterns("Go")
        assert len(patterns) > 0

    def test_loads_java_patterns(self):
        patterns = load_patterns("Java")
        assert len(patterns) > 0

    def test_loads_python_patterns(self):
        patterns = load_patterns("Python")
        assert len(patterns) > 0


class TestLoadFixes:
    def test_loads_fixes(self):
        fixes = load_fixes()
        assert len(fixes) > 0

    def test_fix_has_fields(self):
        fixes = load_fixes()
        fix = fixes[0]
        assert fix.pattern_id
        assert fix.fix_description
        assert fix.explanation


class TestScanSourceCode:
    def test_htole32_critical(self):
        code = "uint32_t le_val = htole32(host_val);"
        result = scan_source_code(code, language="C")
        assert result["critical_count"] >= 1
        assert result["overall_status"] == "REQUIRES CHANGES"

    def test_htons_info(self):
        code = "uint16_t net_val = htons(host_val);"
        result = scan_source_code(code, language="C")
        assert result["critical_count"] == 0
        assert result["info_count"] >= 1

    def test_endian_neutral_code(self):
        code = "int x = 42;\nint y = x + 1;\nreturn y;"
        result = scan_source_code(code, language="C")
        assert result["critical_count"] == 0
        assert result["warning_count"] == 0

    def test_go_little_endian_critical(self):
        code = 'binary.LittleEndian.PutUint32(buf, value)'
        result = scan_source_code(code, language="Go")
        assert result["critical_count"] >= 1

    def test_python_struct_pack_little_endian(self):
        code = "data = struct.pack('<I', value)"
        result = scan_source_code(code, language="Python")
        assert result["critical_count"] >= 1

    def test_python_struct_pack_network_order(self):
        code = "data = struct.pack('!I', value)"
        result = scan_source_code(code, language="Python")
        assert result["critical_count"] == 0

    def test_java_bytebuffer_little_endian(self):
        code = "ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN)"
        result = scan_source_code(code, language="Java")
        assert result["critical_count"] >= 1

    def test_inline_assembly_critical(self):
        code = '__asm__("bswap %0" : "=r"(x) : "0"(x));'
        result = scan_source_code(code, language="C")
        assert result["critical_count"] >= 1

    def test_packed_struct_warning(self):
        code = "struct __attribute__((packed)) Data { uint16_t a; uint32_t b; };"
        result = scan_source_code(code, language="C")
        assert result["warning_count"] >= 1 or result["critical_count"] >= 1

    def test_fix_recommendation_included(self):
        code = "uint32_t le_val = htole32(host_val);"
        result = scan_source_code(code, language="C")
        findings_with_fix = [f for f in result["findings"] if f.get("fix_recommendation")]
        assert len(findings_with_fix) > 0

    def test_multiline_scan(self):
        code = """
#include <stdio.h>
uint32_t le_val = htole32(host_val);
uint16_t net_val = htons(data);
fwrite(&data, sizeof(data), 1, fp);
"""
        result = scan_source_code(code, language="C")
        assert result["critical_count"] >= 1
        assert result["info_count"] >= 1
        assert result["warning_count"] >= 1

    def test_returns_line_numbers(self):
        code = "line1\nline2\nuint32_t le_val = htole32(host_val);\nline4"
        result = scan_source_code(code, language="C")
        assert any(f["line"] == 3 for f in result["findings"])

    def test_total_lines_counted(self):
        code = "line1\nline2\nline3"
        result = scan_source_code(code)
        assert result["total_lines"] == 3
