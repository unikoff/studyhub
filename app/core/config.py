import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JSON_PATH = PROJECT_ROOT / "data" / "tasks.json"
ENV_FILE = PROJECT_ROOT / ".env"


def get_json_path() -> Path:
    load_dotenv(dotenv_path=ENV_FILE, override=False)
    value = os.getenv("JSON_PATH")

    if value is None:
        return DEFAULT_JSON_PATH

    return Path(value)
