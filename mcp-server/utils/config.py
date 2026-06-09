import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(BASE_DIR)

DATA_DIR = os.path.join(SERVER_DIR, "data")
USEARCH_INDEX_PATH = os.path.join(DATA_DIR, "usearch_index.bin")
METADATA_PATH = os.path.join(DATA_DIR, "metadata.json")
SCRIPT_INDEX_PATH = os.path.join(DATA_DIR, "script_index.json")

PATTERNS_DIR = os.path.join(SERVER_DIR, "patterns")

MODEL_NAME = "all-MiniLM-L6-v2"

TARGET_ARCHITECTURES = {"amd64", "s390x"}
DOCKER_REGISTRY_TIMEOUT = 10

WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "/workspace")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
