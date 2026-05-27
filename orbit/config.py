import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _default_path(env_key: str, default: str) -> Path:
    raw = os.getenv(env_key, default)
    path = Path(raw).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        print(f"FATAL: {key} environment variable is required but not set.", file=sys.stderr)
        sys.exit(1)
    return value


def get_openai_api_key() -> str:
    return _require("OPENAI_API_KEY")


def get_exa_api_key() -> str:
    return _require("EXA_API_KEY")


LINKEDIN_SESSION_PATH: Path = _default_path("LINKEDIN_SESSION_PATH", "~/.orbit/linkedin_session")
DATABASE_PATH: Path = _default_path("DATABASE_PATH", "~/.orbit/orbit.db")
MAX_PROSPECTS: int = int(os.getenv("MAX_PROSPECTS", "40"))
SCAN_RATE_LIMIT: int = int(os.getenv("SCAN_RATE_LIMIT", "5"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

if not LINKEDIN_SESSION_PATH.exists():
    print(
        f"WARNING: LinkedIn session not found at {LINKEDIN_SESSION_PATH}. "
        "Run 'orbit-login' to authenticate. Exa-only signals will still work.",
        file=sys.stderr,
    )
