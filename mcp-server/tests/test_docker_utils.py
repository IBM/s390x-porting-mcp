import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.docker_utils import (
    _extract_architectures,
    _parse_image_spec,
    check_docker_image_architectures,
)


class TestParseImageSpec:
    def test_image_with_tag(self):
        repo, tag = _parse_image_spec("nginx:1.25")
        assert repo == "library/nginx"
        assert tag == "1.25"

    def test_image_without_tag(self):
        repo, tag = _parse_image_spec("nginx")
        assert repo == "library/nginx"
        assert tag == "latest"

    def test_namespaced_image(self):
        repo, tag = _parse_image_spec("myorg/myimage:v2")
        assert repo == "myorg/myimage"
        assert tag == "v2"

    def test_namespaced_without_tag(self):
        repo, tag = _parse_image_spec("myorg/myimage")
        assert repo == "myorg/myimage"
        assert tag == "latest"


class TestExtractArchitectures:
    def test_multi_arch_manifest(self):
        manifest = {
            "manifests": [
                {"platform": {"architecture": "amd64", "os": "linux"}},
                {"platform": {"architecture": "arm64", "os": "linux"}},
                {"platform": {"architecture": "s390x", "os": "linux"}},
            ]
        }
        archs = _extract_architectures(manifest)
        assert "linux/amd64" in archs
        assert "linux/arm64" in archs
        assert "linux/s390x" in archs

    def test_single_arch_manifest(self):
        manifest = {"config": {"mediaType": "application/vnd.docker.container.image.v1+json"}}
        archs = _extract_architectures(manifest)
        assert len(archs) >= 1

    def test_filters_unknown_arch(self):
        manifest = {
            "manifests": [
                {"platform": {"architecture": "amd64", "os": "linux"}},
                {"platform": {"architecture": "unknown", "os": "unknown"}},
            ]
        }
        archs = _extract_architectures(manifest)
        assert "unknown/unknown" not in archs
        assert len(archs) == 1


class TestCheckDockerImageArchitectures:
    @patch("utils.docker_utils._get_manifest")
    @patch("utils.docker_utils._get_auth_token")
    def test_s390x_supported(self, mock_token, mock_manifest):
        mock_token.return_value = "fake-token"
        mock_manifest.return_value = {
            "manifests": [
                {"platform": {"architecture": "amd64", "os": "linux"}},
                {"platform": {"architecture": "s390x", "os": "linux"}},
            ]
        }
        result = check_docker_image_architectures("nginx:latest")
        assert result["status"] == "success"
        assert result["s390x_supported"] is True

    @patch("utils.docker_utils._get_manifest")
    @patch("utils.docker_utils._get_auth_token")
    def test_s390x_not_supported(self, mock_token, mock_manifest):
        mock_token.return_value = "fake-token"
        mock_manifest.return_value = {
            "manifests": [
                {"platform": {"architecture": "amd64", "os": "linux"}},
                {"platform": {"architecture": "arm64", "os": "linux"}},
            ]
        }
        result = check_docker_image_architectures("someimage:latest")
        assert result["status"] == "success"
        assert result["s390x_supported"] is False

    @patch("utils.docker_utils._get_auth_token")
    def test_network_error(self, mock_token):
        import requests
        mock_token.side_effect = requests.exceptions.ConnectionError("connection failed")
        result = check_docker_image_architectures("bad:image")
        assert result["status"] == "error"
        assert result["s390x_supported"] is False
