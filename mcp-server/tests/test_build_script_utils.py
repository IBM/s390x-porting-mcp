import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.build_script_utils import (
    _distro_matches,
    _find_package,
    _find_version,
    _normalize_name,
    find_and_return_script,
)

SAMPLE_INDEX = {
    "Apache-Kafka": {
        "wiki_url": "https://example.com/kafka",
        "versions": {
            "3.7.0": {
                "scripts": [
                    {
                        "script_url": "https://example.com/kafka-3.7.0.sh",
                        "filename": "build_kafka.sh",
                    },
                ],
                "distros": ["Ubuntu 22.04", "RHEL 8"],
            },
            "3.6.0": {
                "scripts": [
                    {
                        "script_url": "https://example.com/kafka-3.6.0.sh",
                        "filename": "build_kafka.sh",
                    },
                ],
                "distros": ["SLES 15"],
            },
        },
    },
    "Go": {
        "wiki_url": "https://example.com/go",
        "versions": {
            "1.22": {
                "scripts": [
                    {
                        "script_url": "https://example.com/go-1.22.sh",
                        "filename": "build_go.sh",
                    },
                ],
                "distros": ["Ubuntu 24.04"],
            },
        },
    },
    "Zabbix": {
        "wiki_url": "",
        "versions": {
            "7.0.25": {
                "scripts": [
                    {
                        "script_url": "https://example.com/build_zabbixagent.sh",
                        "filename": "build_zabbixagent.sh",
                    },
                    {
                        "script_url": "https://example.com/build_zabbixserver.sh",
                        "filename": "build_zabbixserver.sh",
                    },
                ],
                "distros": ["Ubuntu 22.04", "RHEL 9"],
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
        assert result["script_url"] == "https://example.com/kafka-3.7.0.sh"
        assert len(result["scripts"]) == 1

    @patch("utils.build_script_utils._load_script_index", return_value=SAMPLE_INDEX)
    def test_multiple_scripts_per_version(self, _):
        result = find_and_return_script("zabbix", "7.0.25")
        assert result["status"] == "found"
        assert result["package"] == "Zabbix"
        assert len(result["scripts"]) == 2
        filenames = [s["filename"] for s in result["scripts"]]
        assert "build_zabbixagent.sh" in filenames
        assert "build_zabbixserver.sh" in filenames
        assert result["script_url"] == result["scripts"][0]["script_url"]

    @patch("utils.build_script_utils._load_script_index", return_value=SAMPLE_INDEX)
    def test_version_not_found(self, _):
        result = find_and_return_script("kafka", "99.0")
        assert result["status"] == "version_not_found"
        assert "available_versions" in result

    @patch("utils.build_script_utils._load_script_index", return_value=SAMPLE_INDEX)
    def test_not_found_suggests_porting(self, _):
        result = find_and_return_script("nonexistent")
        assert result["status"] == "not_found"
        assert "suggestion" in result
        assert "port_analysis" in result["suggestion"]
        assert "contact" in result
        assert "community.ibm.com/zsystems/oss" in result["contact"]
