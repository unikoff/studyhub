from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL, make_url

from app import main as main_module
from app.api import app
from app.cli import execute_command
from app.core import config
from app.storage import JsonStorage, MemoryStorage


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.delenv("JSON_PATH", raising=False)
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    return tmp_path


def test_load_settings_uses_defaults_when_values_are_absent(isolated_config):
    settings = config.load_settings(environ={}, project_root=isolated_config)

    assert settings.json_path == (isolated_config / "data" / "tasks.json").resolve()
    assert settings.app_name == "StudyHub Planner"
    assert settings.cookie_secure is False
    database_url = make_url(settings.database_url)
    assert database_url.get_backend_name() == "sqlite"
    assert Path(database_url.database) == (
        isolated_config / "data" / "studyhub.sqlite3"
    )


def test_database_default_stays_under_project_root_after_changing_cwd(
    isolated_config, monkeypatch
):
    monkeypatch.chdir(isolated_config)
    first = config.load_settings(environ={}, project_root=isolated_config)

    other_cwd = isolated_config / "other-cwd"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)
    second = config.load_settings(environ={}, project_root=isolated_config)

    expected = (isolated_config / "data" / "studyhub.sqlite3").resolve()
    assert Path(make_url(first.database_url).database) == expected
    assert Path(make_url(second.database_url).database) == expected
    assert not expected.exists()


def test_load_settings_resolves_explicit_relative_database_url(isolated_config):
    settings = config.load_settings(
        environ={"DATABASE_URL": "sqlite:///data/custom.sqlite3"},
        project_root=isolated_config,
    )

    assert Path(make_url(settings.database_url).database) == (
        isolated_config / "data" / "custom.sqlite3"
    ).resolve()


def test_load_settings_preserves_explicit_absolute_database_url(isolated_config):
    database_path = isolated_config / "outside" / "custom.sqlite3"
    raw_url = URL.create(
        "sqlite", database=database_path.as_posix()
    ).render_as_string(hide_password=False)

    settings = config.load_settings(
        environ={"DATABASE_URL": raw_url},
        project_root=isolated_config,
    )

    assert Path(make_url(settings.database_url).database) == database_path
    assert not database_path.exists()


@pytest.mark.parametrize(
    "raw_database_url",
    [
        "",
        "   ",
        "postgresql://localhost/planner",
        "sqlite:///:memory:",
        "sqlite://",
    ],
)
def test_load_settings_rejects_empty_or_unsupported_database_url(
    isolated_config, raw_database_url
):
    with pytest.raises(ValueError, match="DATABASE_URL"):
        config.load_settings(
            environ={"DATABASE_URL": raw_database_url},
            project_root=isolated_config,
        )


def test_load_settings_rejects_invalid_database_url(isolated_config):
    with pytest.raises(ValueError, match="DATABASE_URL"):
        config.load_settings(
            environ={"DATABASE_URL": "not-a-sqlite-url"},
            project_root=isolated_config,
        )


def test_database_url_process_environment_overrides_dotenv(
    isolated_config, monkeypatch
):
    config.ENV_FILE.write_text(
        "DATABASE_URL=sqlite:///data/from-file.sqlite3\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "DATABASE_URL", "sqlite:///data/from-process.sqlite3"
    )

    settings = config.load_settings(project_root=isolated_config)

    assert Path(make_url(settings.database_url).database) == (
        isolated_config / "data" / "from-process.sqlite3"
    ).resolve()


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("true", True),
        (" TRUE ", True),
        ("false", False),
        (" False ", False),
    ],
)
def test_load_settings_parses_cookie_secure(
    isolated_config, raw_value, expected
):
    settings = config.load_settings(
        environ={"COOKIE_SECURE": raw_value},
        project_root=isolated_config,
    )

    assert settings.cookie_secure is expected


@pytest.mark.parametrize("raw_value", ["", "   ", "yes"])
def test_load_settings_rejects_invalid_cookie_secure(
    isolated_config, raw_value
):
    with pytest.raises(ValueError, match="COOKIE_SECURE"):
        config.load_settings(
            environ={"COOKIE_SECURE": raw_value},
            project_root=isolated_config,
        )


def test_load_settings_resolves_relative_path_from_project_root(
    isolated_config, monkeypatch
):
    monkeypatch.chdir(isolated_config)
    first = config.load_settings(
        environ={"JSON_PATH": "data/custom.json"},
        project_root=isolated_config,
    )

    other_cwd = isolated_config / "other-cwd"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)
    second = config.load_settings(
        environ={"JSON_PATH": "data/custom.json"},
        project_root=isolated_config,
    )

    expected = (isolated_config / "data" / "custom.json").resolve()
    assert first.json_path == expected
    assert second.json_path == expected


def test_load_settings_preserves_absolute_path(isolated_config, tmp_path):
    selected_path = tmp_path / "outside" / "tasks.json"

    settings = config.load_settings(
        environ={"JSON_PATH": str(selected_path)},
        project_root=isolated_config,
    )

    assert settings.json_path == selected_path


@pytest.mark.parametrize("key", ["JSON_PATH", "APP_NAME"])
@pytest.mark.parametrize("value", ["", "   "])
def test_load_settings_rejects_empty_values_by_name(
    isolated_config, key, value
):
    with pytest.raises(ValueError, match=key):
        config.load_settings(environ={key: value}, project_root=isolated_config)


def test_load_settings_rejects_existing_directory(isolated_config):
    folder = isolated_config / "tasks-folder"
    folder.mkdir()

    with pytest.raises(ValueError, match="JSON_PATH"):
        config.load_settings(
            environ={"JSON_PATH": str(folder)},
            project_root=isolated_config,
        )


def test_load_settings_keeps_process_environment_priority(
    isolated_config, monkeypatch
):
    file_path = isolated_config / "from-file.json"
    process_path = isolated_config / "from-process.json"
    config.ENV_FILE.write_text(
        f"JSON_PATH={file_path.as_posix()}\n"
        "DATABASE_URL=sqlite:///data/from-file.sqlite3\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("JSON_PATH", str(process_path))
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/from-process.sqlite3")

    settings = config.load_settings(project_root=isolated_config)

    assert settings.json_path == process_path
    assert settings.app_name == "StudyHub Planner"
    assert Path(make_url(settings.database_url).database) == (
        isolated_config / "data" / "from-process.sqlite3"
    ).resolve()


def test_explicit_environment_does_not_read_dotenv(isolated_config):
    config.ENV_FILE.write_text(
        "JSON_PATH=from-file.json\nAPP_NAME=From file\n",
        encoding="utf-8",
    )

    settings = config.load_settings(
        environ={"APP_NAME": "Explicit"},
        project_root=isolated_config,
    )

    assert settings.json_path == (isolated_config / "data" / "tasks.json").resolve()
    assert settings.app_name == "Explicit"


def test_build_service_uses_settings_and_preserves_explicit_storage(
    isolated_config, monkeypatch
):
    selected_path = isolated_config / "selected.json"
    settings = config.Settings(json_path=selected_path, app_name="Test Planner")

    service = main_module.build_service(settings=settings)

    assert service.storage.path == selected_path
    assert not selected_path.exists()
    assert isinstance(service.storage, JsonStorage)
    assert not Path(make_url(settings.database_url).database).exists()

    storage = MemoryStorage()
    monkeypatch.setenv("JSON_PATH", "")
    monkeypatch.setenv("APP_NAME", "")

    assert main_module.build_service(storage).storage is storage


def test_api_and_cli_share_loaded_settings_and_json(
    isolated_config, monkeypatch
):
    selected_path = isolated_config / "selected.json"
    config.ENV_FILE.write_text(
        f"JSON_PATH={selected_path.as_posix()}\nAPP_NAME=StudyHub Test\n",
        encoding="utf-8",
    )
    settings = config.load_settings(project_root=isolated_config)
    previous_settings = app.state.settings
    previous_service = app.state.planner

    try:
        app.state.settings = settings
        app.state.planner = main_module.build_service(settings=settings)
        with TestClient(app, follow_redirects=False) as client:
            response = client.post(
                "/tasks",
                json={"title": "Изолированная задача", "priority": 2},
            )
            assert response.status_code == 201, response.text

        assert selected_path.exists()

        messages = []
        cli_service = main_module.build_service(settings=settings)
        execute_command(
            cli_service,
            "list",
            read=lambda _prompt: "",
            write=messages.append,
        )
        assert any("изолированная задача" in message.casefold() for message in messages)
    finally:
        app.state.settings = previous_settings
        app.state.planner = previous_service
