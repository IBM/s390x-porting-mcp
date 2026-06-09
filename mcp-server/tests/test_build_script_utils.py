import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.build_script_utils import (
    _normalize_name,
    _find_package,
    _find_version,
    _distro_matches,
    find_and_return_script,
)

SAMPLE_INDEX = {
    "Apache-Kafka": {
        "wiki_url": "https://example.com/kafka",
        "versions": {
            "3.7.0": {
                "script_url": "https://example.com/kafka-3.7.0.sh",
                "distros": ["Ubuntu 22.04", "RHEL 8"],
                "script_content": "#!/bin/bash\necho kafka",
            },
            "3.6.0": {
                "script_url": "https://example.com/kafka-3.6.0.sh",
                "distros": ["SLES 15"],
                "script_content": "#!/bin/bash\necho kafka old",
            },
        },
    },
    "Go": {
        "wiki_url": "https://example.com/go",
        "versions": {
            "1.22": {
                "script_url": "https://example.com/go-1.22.sh",
                "distros": ["Ubuntu 24.04"],
                "script_content": "#!/bin/bash\necho go",
            },
        },
    },
}


class TestNormalizeName:
    def test_lowercase_and_strip(self):
        assert _normalize_name("Apache-Kafka") == "apachekafka"

    def test_already_normalized(self):
        assert _normalize_name("kafka") == "kafka"

    def test_special_chars(self):
        assert _normalize_name("node.js") == "nodejs"


class TestDistroMatches:
    def test_match(self):
        ver_data = {"distros": ["Ubuntu 22.04", "RHEL 8"]}
        assert _distro_matches(ver_data, "ubuntu") is True

    def test_no_match(self):
        ver_data = {"distros": ["SLES 15"]}
        assert _distro_matches(ver_data, "ubuntu") is False

    def test_empty_distros(self):
        assert _distro_matches({}, "ubuntu") is False


class TestFindPackage:
    @patch("utils.build_script_utils._load_script_index", return_value=SAMPLE_INDEX)
    def test_exact_match(self, _):
        result = _find_package("Apache-Kafka")
        assert result is not None
        assert result[0] == "Apache-Kafka"

    @patch("utils.build_script_utils._load_script_index", return_value=SAMPLE_INDEX)
    def test_case_insensitive(self, _):
        result = _find_package("apache-kafka")
        assert result is not None
        assert result[0] == "Apache-Kafka"

    @patch("utils.build_script_utils._load_script_index", return_value=SAMPLE_INDEX)
    def test_partial_match(self, _):
        result = _find_package("kafka")
        assert result is not None
        assert result[0] == "Apache-Kafka"

    @patch("utils.build_script_utils._load_script_index", return_value=SAMPLE_INDEX)
    def test_not_found(self, _):
        result = _find_package("nonexistent")
        assert result is None


class TestFindVersion:
    def test_exact_version(self):
        result = _find_version(SAMPLE_INDEX["Apache-Kafka"], "3.7.0")
        assert result is not None
        assert result[0] == "3.7.0"

    def test_prefix_match(self):
        result = _find_version(SAMPLE_INDEX["Apache-Kafka"], "3.7")
        assert result is not None
        assert result[0] == "3.7.0"

    def test_latest_when_none(self):
        result = _find_version(SAMPLE_INDEX["Apache-Kafka"])
        assert result is not None
        assert result[0] == "3.7.0"

    def test_version_not_found(self):
        result = _find_version(SAMPLE_INDEX["Apache-Kafka"], "99.0")
        assert result is None

    def test_empty_versions(self):
        result = _find_version({"versions": {}})
        assert result is None

    def test_distro_preferred_when_no_version(self):
        result = _find_version(SAMPLE_INDEX["Apache-Kafka"], distro="sles")
        assert result is not None
        assert result[0] == "3.6.0"

    def test_distro_fallback_to_latest(self):
        result = _find_version(SAMPLE_INDEX["Apache-Kafka"], distro="debian")
        assert result is not None
        assert result[0] == "3.7.0"


class TestFindAndReturnScript:
    @patch("utils.build_script_utils._load_script_index", return_value=SAMPLE_INDEX)
    def test_found(self, _):
        result = find_and_return_script("kafka", "3.7.0")
        assert result["status"] == "found"
        assert result["package"] == "Apache-Kafka"
        assert result["version"] == "3.7.0"
        assert "script_content" in result

    @patch("utils.build_script_utils._load_script_index", return_value=SAMPLE_INDEX)
    def test_version_not_found(self, _):
        result = find_and_return_script("kafka", "99.0")
        assert result["status"] == "version_not_found"
        assert "available_versions" in result

    @patch("utils.build_script_utils._load_script_index", return_value=SAMPLE_INDEX)
    def test_not_found_with_kb_fallback(self, _):
        result = find_and_return_script("nonexistent")
        assert result["status"] in ("not_found", "not_found_in_scripts")

    @patch("utils.kb_search_utils.search_knowledge_base", side_effect=Exception("no kb"))
    @patch("utils.build_script_utils._load_script_index", return_value=SAMPLE_INDEX)
    def test_not_found_no_kb(self, *_):
        result = find_and_return_script("nonexistent")
        assert result["status"] == "not_found"
