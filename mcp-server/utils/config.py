import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(BASE_DIR)

DATA_DIR = os.path.join(SERVER_DIR, "data")
USEARCH_INDEX_PATH = os.path.join(DATA_DIR, "usearch_index.bin")
METADATA_PATH = os.path.join(DATA_DIR, "metadata.json")
SCRIPT_INDEX_PATH = os.path.join(DATA_DIR, "script_index.json")


def _count_script_packages() -> int:
    try:
        with open(SCRIPT_INDEX_PATH) as f:
            return len(json.load(f))
    except Exception:
        return 0


def _count_kb_packages() -> int:
    try:
        with open(METADATA_PATH) as f:
            entries = json.load(f)
        return len({e.get("product", "") for e in entries if e.get("product")})
    except Exception:
        return 0


SCRIPT_PACKAGE_COUNT = _count_script_packages()
KB_PACKAGE_COUNT = _count_kb_packages()

PATTERNS_DIR = os.path.join(SERVER_DIR, "patterns")

MODEL_NAME = "all-MiniLM-L6-v2"

TARGET_ARCHITECTURES = {"amd64", "s390x"}
DOCKER_REGISTRY_TIMEOUT = 10

WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "/workspace")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
