from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.api import app
from app.cli import execute_command
from app.core import config
from app.storage import MemoryStorage


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.delenv("JSON_PATH", raising=False)
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    return tmp_path


def test_load_settings_uses_defaults_when_values_are_absent(isolated_config):
    settings = config.load_settings(environ={}, project_root=isolated_config)

    assert settings.json_path == (isolated_config / "data" / "tasks.json").resolve()
    assert settings.app_name == "StudyHub Planner"


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
        f"JSON_PATH={file_path.as_posix()}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("JSON_PATH", str(process_path))

    settings = config.load_settings(project_root=isolated_config)

    assert settings.json_path == process_path
    assert settings.app_name == "StudyHub Planner"


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
