import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.skopeo_tool import skopeo_inspect, skopeo_help
from utils.cli_utils import run_command


class TestRunCommand:
    @patch("utils.cli_utils.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="output", stderr=""
        )
        result = run_command(["echo", "hello"])
        assert result["status"] == "success"
        assert result["stdout"] == "output"

    @patch("utils.cli_utils.subprocess.run")
    def test_nonzero_exit(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="error"
        )
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
        mock_cmd.assert_called_once_with(
            ["skopeo", "inspect", "docker://nginx:latest"]
        )

    @patch("utils.skopeo_tool.run_command")
    def test_raw_inspect(self, mock_cmd):
        mock_cmd.return_value = {"status": "success", "stdout": "{}"}
        skopeo_inspect("nginx:latest", raw=True)
        mock_cmd.assert_called_once_with(
            ["skopeo", "inspect", "--raw", "docker://nginx:latest"]
        )

    @patch("utils.skopeo_tool.run_command")
    def test_custom_transport(self, mock_cmd):
        mock_cmd.return_value = {"status": "success", "stdout": "{}"}
        skopeo_inspect("dir/image", transport="dir")
        mock_cmd.assert_called_once_with(
            ["skopeo", "inspect", "dir://dir/image"]
        )


class TestSkopeoHelp:
    @patch("utils.skopeo_tool.run_command")
    def test_help(self, mock_cmd):
        mock_cmd.return_value = {"status": "success", "stdout": "skopeo usage..."}
        result = skopeo_help()
        mock_cmd.assert_called_once_with(["skopeo", "--help"])
        assert result["status"] == "success"
