from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JSON_PATH = Path("data/tasks.json")
DEFAULT_APP_NAME = "StudyHub Planner"
DEFAULT_COOKIE_SECURE = False
DEFAULT_DATABASE_RELATIVE_PATH = Path("data/studyhub.sqlite3")
ENV_FILE = PROJECT_ROOT / ".env"


def default_database_url(project_root: Path) -> str:
    database_path = (project_root / DEFAULT_DATABASE_RELATIVE_PATH).resolve()
    return URL.create("sqlite", database=database_path.as_posix()).render_as_string(
        hide_password=False
    )


DEFAULT_DATABASE_URL = default_database_url(PROJECT_ROOT)


@dataclass
class Settings:
    json_path: Path
    app_name: str
    cookie_secure: bool = DEFAULT_COOKIE_SECURE
    database_url: str = DEFAULT_DATABASE_URL


def parse_cookie_secure(raw: str | None) -> bool:
    if raw is None:
        return DEFAULT_COOKIE_SECURE

    value = raw.strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError("COOKIE_SECURE must be 'true' or 'false'")


def resolve_database_url(raw_url: str, project_root: Path) -> str:
    try:
        url = make_url(raw_url)
    except ArgumentError as error:
        raise ValueError("DATABASE_URL is invalid") from error

    if url.drivername not in {"sqlite", "sqlite+pysqlite"}:
        raise ValueError("DATABASE_URL must use file-based SQLite")
    if url.host is not None or url.username is not None or url.password is not None:
        raise ValueError("DATABASE_URL must point to a local SQLite file")

    database = url.database
    if not database or database == ":memory:" or database.startswith("file:"):
        raise ValueError("DATABASE_URL must include a SQLite file path")

    database_path = Path(database)
    if not database_path.is_absolute():
        database_path = project_root / database_path
    database_path = database_path.resolve()
    return url.set(database=database_path.as_posix()).render_as_string(
        hide_password=False
    )


def load_settings(
    environ: Mapping[str, str] | None = None,
    project_root: Path = PROJECT_ROOT,
) -> Settings:
    if environ is None:
        load_dotenv(dotenv_path=ENV_FILE, override=False)
        values = os.environ
    else:
        values = environ

    raw_path = values.get("JSON_PATH")
    if raw_path is None:
        raw_path = str(DEFAULT_JSON_PATH)
    elif not raw_path.strip():
        raise ValueError("JSON_PATH must not be empty")

    json_path = Path(raw_path)
    if not json_path.is_absolute():
        json_path = (project_root / json_path).resolve()
    if json_path.exists() and json_path.is_dir():
        raise ValueError("JSON_PATH must point to a file, not a directory")

    raw_name = values.get("APP_NAME")
    if raw_name is None:
        app_name = DEFAULT_APP_NAME
    elif not raw_name.strip():
        raise ValueError("APP_NAME must not be empty")
    else:
        app_name = raw_name

    cookie_secure = parse_cookie_secure(values.get("COOKIE_SECURE"))

    raw_database_url = values.get("DATABASE_URL")
    if raw_database_url is None:
        database_url = default_database_url(project_root)
    elif not raw_database_url.strip():
        raise ValueError("DATABASE_URL must not be empty")
    else:
        database_url = resolve_database_url(raw_database_url, project_root)

    return Settings(
        json_path=json_path,
        app_name=app_name,
        cookie_secure=cookie_secure,
        database_url=database_url,
    )
