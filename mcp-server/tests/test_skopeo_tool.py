import os
import socket
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.cli_utils import run_command
from utils.skopeo_tool import skopeo_help, skopeo_inspect


class TestRunCommand:
    @patch("utils.cli_utils.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="output", stderr="")
        result = run_command(["echo", "hello"])
        assert result["status"] == "success"
        assert result["stdout"] == "output"

    @patch("utils.cli_utils.subprocess.run")
    def test_nonzero_exit(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        result = run_command(["false"])
        assert result["status"] == "error"
        assert result["returncode"] == 1

    @patch("utils.cli_utils.subprocess.run")
    def test_timeout(self, mock_run):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="cmd", timeout=10)
        result = run_command(["sleep", "100"], timeout=10)
        assert result["status"] == "error"
        assert "timed out" in result["error"]

    @patch("utils.cli_utils.subprocess.run")
    def test_command_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        result = run_command(["nonexistent"])
        assert result["status"] == "error"
        assert "not found" in result["error"]


class TestSkopeoInspect:
    @patch("utils.skopeo_tool.run_command")
    def test_basic_inspect(self, mock_cmd):
        mock_cmd.return_value = {"status": "success", "stdout": "{}"}
        skopeo_inspect("nginx:latest")
        mock_cmd.assert_called_once_with(["skopeo", "inspect", "docker://nginx:latest"])

    @patch("utils.skopeo_tool.run_command")
    def test_raw_inspect(self, mock_cmd):
        mock_cmd.return_value = {"status": "success", "stdout": "{}"}
        skopeo_inspect("nginx:latest", raw=True)
        mock_cmd.assert_called_once_with(["skopeo", "inspect", "--raw", "docker://nginx:latest"])

    def test_custom_transport_blocked(self):
        result = skopeo_inspect("dir/image", transport="dir")
        assert result["status"] == "error"
        assert "Unsupported transport" in result["error"]


class TestTransportValidation:
    @patch("utils.skopeo_tool.run_command")
    def test_docker_transport_allowed(self, mock_cmd):
        mock_cmd.return_value = {"status": "success", "stdout": "{}"}
        result = skopeo_inspect("nginx:latest", transport="docker")
        mock_cmd.assert_called_once_with(["skopeo", "inspect", "docker://nginx:latest"])
        assert result["status"] == "success"

    def test_dir_transport_blocked(self):
        result = skopeo_inspect("/etc/passwd", transport="dir")
        assert result["status"] == "error"
        assert "Unsupported transport" in result["error"]

    def test_docker_daemon_transport_blocked(self):
        result = skopeo_inspect("nginx:latest", transport="docker-daemon")
        assert result["status"] == "error"
        assert "Unsupported transport" in result["error"]

    def test_oci_transport_blocked(self):
        result = skopeo_inspect("/tmp/oci-image", transport="oci")
        assert result["status"] == "error"
        assert "Unsupported transport" in result["error"]

    def test_containers_storage_transport_blocked(self):
        result = skopeo_inspect("nginx:latest", transport="containers-storage")
        assert result["status"] == "error"
        assert "Unsupported transport" in result["error"]


class TestSkopeoHelp:
    @patch("utils.skopeo_tool.run_command")
    def test_help(self, mock_cmd):
        mock_cmd.return_value = {"status": "success", "stdout": "skopeo usage..."}
        result = skopeo_help()
        mock_cmd.assert_called_once_with(["skopeo", "--help"])
        assert result["status"] == "success"


class TestHostValidation:
    def test_cloud_metadata_ip_blocked(self):
        result = skopeo_inspect("169.254.169.254/probe:latest")
        assert result["status"] == "error"

    def test_link_local_ip_blocked(self):
        result = skopeo_inspect("169.254.1.1/probe:latest")
        assert result["status"] == "error"

    def test_zero_ip_blocked(self):
        result = skopeo_inspect("0.0.0.0/probe:latest")
        assert result["status"] == "error"

    def test_metadata_google_hostname_blocked(self):
        result = skopeo_inspect("metadata.google.internal/probe:latest")
        assert result["status"] == "error"

    @patch("utils.skopeo_tool.run_command")
    def test_localhost_allowed(self, mock_cmd):
        mock_cmd.return_value = {"status": "success", "stdout": "{}"}
        result = skopeo_inspect("localhost:5000/myimage:latest")
        mock_cmd.assert_called_once()
        assert result["status"] == "success"

    @patch("utils.skopeo_tool.run_command")
    @patch("utils.skopeo_tool.socket.getaddrinfo")
    def test_private_ip_allowed(self, mock_dns, mock_cmd):
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443)),
        ]
        mock_cmd.return_value = {"status": "success", "stdout": "{}"}
        result = skopeo_inspect("registry.corp.example.com/myimage:latest")
        mock_cmd.assert_called_once()
        assert result["status"] == "success"

    @patch("utils.skopeo_tool.run_command")
    def test_dockerhub_implicit_host_allowed(self, mock_cmd):
        mock_cmd.return_value = {"status": "success", "stdout": "{}"}
        result = skopeo_inspect("alpine:latest")
        mock_cmd.assert_called_once()
        assert result["status"] == "success"

    @patch("utils.skopeo_tool.run_command")
    @patch("utils.skopeo_tool.socket.getaddrinfo")
    def test_quay_registry_allowed(self, mock_dns, mock_cmd):
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("54.198.86.24", 443)),
        ]
        mock_cmd.return_value = {"status": "success", "stdout": "{}"}
        result = skopeo_inspect("quay.io/ibm/myimage:latest")
        mock_cmd.assert_called_once()
        assert result["status"] == "success"

    @patch("utils.skopeo_tool.socket.getaddrinfo")
    def test_dns_resolution_failure_blocked(self, mock_dns):
        mock_dns.side_effect = socket.gaierror("Name or service not known")
        result = skopeo_inspect("nonexistent.invalid/probe:latest")
        assert result["status"] == "error"

    def test_ipv6_link_local_blocked(self):
        result = skopeo_inspect("[fe80::1]/probe:latest")
        assert result["status"] == "error"


class TestImageFormatValidation:
    def test_empty_image_rejected(self):
        result = skopeo_inspect("")
        assert result["status"] == "error"
        assert "Invalid image" in result["error"]

    def test_image_with_spaces_rejected(self):
        result = skopeo_inspect("alpine latest")
        assert result["status"] == "error"
        assert "Invalid image" in result["error"]

    def test_image_with_control_chars_rejected(self):
        result = skopeo_inspect("alpine\x00:latest")
        assert result["status"] == "error"
        assert "Invalid image" in result["error"]

    def test_image_with_semicolon_rejected(self):
        result = skopeo_inspect("alpine;echo pwned")
        assert result["status"] == "error"
        assert "Invalid image" in result["error"]

    @patch("utils.skopeo_tool.run_command")
    def test_valid_image_simple(self, mock_cmd):
        mock_cmd.return_value = {"status": "success", "stdout": "{}"}
        result = skopeo_inspect("alpine:latest")
        mock_cmd.assert_called_once()
        assert result["status"] == "success"

    @patch("utils.skopeo_tool.run_command")
    @patch("utils.skopeo_tool.socket.getaddrinfo")
    def test_valid_image_with_registry(self, mock_dns, mock_cmd):
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("54.198.86.24", 443)),
        ]
        mock_cmd.return_value = {"status": "success", "stdout": "{}"}
        result = skopeo_inspect("quay.io/ibm/s390x-mcp:latest")
        mock_cmd.assert_called_once()
        assert result["status"] == "success"

    @patch("utils.skopeo_tool.run_command")
    def test_valid_image_with_digest(self, mock_cmd):
        mock_cmd.return_value = {"status": "success", "stdout": "{}"}
        result = skopeo_inspect(
            "alpine@sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        )
        mock_cmd.assert_called_once()
        assert result["status"] == "success"

    @patch("utils.skopeo_tool.run_command")
    def test_valid_image_with_port(self, mock_cmd):
        mock_cmd.return_value = {"status": "success", "stdout": "{}"}
        result = skopeo_inspect("localhost:5000/myimage:v1")
        mock_cmd.assert_called_once()
        assert result["status"] == "success"
