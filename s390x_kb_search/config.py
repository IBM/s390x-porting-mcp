import re

DISTANCE_THRESHOLD = 1.1
K_RESULTS = 5
RRF_K = 60

SEARCH_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9_\-+.]*", re.IGNORECASE)

S390X_STOPWORDS = {
    "s390x", "ibm", "z", "linux", "mainframe", "build", "building",
    "install", "installing", "port", "porting", "on", "for", "the",
    "how", "to", "do", "i", "a", "an", "is", "it", "can",
}

BUILD_GUIDE_INTENT_TOKENS = {
    "build", "building", "compile", "compiling", "install", "installing",
    "setup", "configure", "dependencies", "prerequisites", "make",
}

BUILD_SCRIPT_INTENT_TOKENS = {
    "script", "automated", "bash", "shell", "automate", "automation",
}

PORTING_INTENT_TOKENS = {
    "port", "porting", "endian", "big-endian", "little-endian",
    "migrate", "migration", "compatibility", "architecture",
    "fix", "patch", "workaround", "issue", "error", "fail", "failure",
    "broken", "crash", "bug",
}

DISTRO_TOKENS = {
    "ubuntu", "rhel", "sles", "suse", "redhat", "debian",
}
