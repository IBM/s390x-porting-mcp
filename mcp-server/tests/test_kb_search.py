import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from s390x_kb_search.resources import SearchResources
from s390x_kb_search.search import (
    _detect_distro,
    _detect_intent,
    _token_overlap,
    deduplicate_urls,
    reciprocal_rank_fusion,
    salient_tokens,
    tokenize,
)


class TestTokenize:
    def test_basic(self):
        tokens = tokenize("How to build Grafana on s390x")
        assert "grafana" in tokens
        assert "s390x" in tokens
        assert "build" in tokens

    def test_handles_special_chars(self):
        tokens = tokenize("c++ python3.13")
        assert "c++" in tokens
        assert "python3.13" in tokens

    def test_empty_string(self):
        assert tokenize("") == []


class TestSalientTokens:
    def test_removes_stopwords(self):
        tokens = salient_tokens("how to build grafana on s390x linux")
        assert "grafana" in tokens
        assert "how" not in tokens
        assert "to" not in tokens
        assert "s390x" not in tokens
        assert "linux" not in tokens

    def test_keeps_package_names(self):
        tokens = salient_tokens("build postgresql on ubuntu")
        assert "postgresql" in tokens
        assert "ubuntu" in tokens


class TestTokenOverlap:
    def test_full_overlap(self):
        assert _token_overlap({"a", "b"}, {"a", "b"}) == 1.0

    def test_no_overlap(self):
        assert _token_overlap({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        assert _token_overlap({"a", "b"}, {"b", "c"}) == 0.5

    def test_empty_sets(self):
        assert _token_overlap(set(), {"a"}) == 0.0


class TestDetectIntent:
    def test_build_intent(self):
        assert _detect_intent({"build", "grafana"}) == "Build Guide"

    def test_fix_intent(self):
        assert _detect_intent({"fix", "cassandra"}) == "Build Guide"

    def test_porting_intent(self):
        assert _detect_intent({"porting", "endian"}) == "Build Guide"

    def test_script_intent(self):
        assert _detect_intent({"script", "automated"}) == "Build Script"

    def test_no_intent(self):
        assert _detect_intent({"grafana", "version"}) is None


class TestDetectDistro:
    def test_ubuntu(self):
        assert _detect_distro({"ubuntu", "24.04"}) == "ubuntu"

    def test_rhel(self):
        assert _detect_distro({"rhel", "9.4"}) == "rhel"

    def test_no_distro(self):
        assert _detect_distro({"build", "grafana"}) is None


class TestRRF:
    def test_merges_results(self):
        dense = [(0, 0.1), (1, 0.2), (2, 0.3)]
        sparse = [(1, 5.0), (2, 4.0), (3, 3.0)]
        fused = reciprocal_rank_fusion(dense, sparse)
        assert 1 in fused
        assert fused[1] > fused[0]

    def test_empty_inputs(self):
        fused = reciprocal_rank_fusion([], [])
        assert len(fused) == 0


class TestDeduplication:
    def test_deduplicates_by_url(self):
        metadata = [
            {"url": "http://a.com"},
            {"url": "http://a.com"},
            {"url": "http://b.com"},
        ]
        resources = SearchResources(metadata=metadata, embedding_model=None)
        results = [(0, 1.0), (1, 0.9), (2, 0.8)]
        deduped = deduplicate_urls(results, resources)
        urls = [resources.metadata[idx]["url"] for idx, _ in deduped]
        assert urls == ["http://a.com", "http://b.com"]
