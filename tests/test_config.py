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
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    return tmp_path


def test_json_path_uses_default_when_process_and_env_file_are_absent(
    isolated_config, monkeypatch
):
    default_path = isolated_config / "default" / "tasks.json"
    monkeypatch.setattr(config, "DEFAULT_JSON_PATH", default_path)

    path = config.get_json_path()

    assert path == default_path


def test_json_path_reads_value_from_explicit_env_file(isolated_config):
    selected_path = isolated_config / "from-file" / "tasks.json"
    config.ENV_FILE.write_text(
        f"JSON_PATH={selected_path.as_posix()}\n",
        encoding="utf-8",
    )

    path = config.get_json_path()

    assert path == selected_path


def test_process_environment_overrides_env_file(isolated_config, monkeypatch):
    file_path = isolated_config / "from-file.json"
    process_path = isolated_config / "from-process.json"
    config.ENV_FILE.write_text(
        f"JSON_PATH={file_path.as_posix()}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("JSON_PATH", str(process_path))

    path = config.get_json_path()

    assert path == process_path


def test_empty_json_path_is_not_replaced_with_the_default(
    isolated_config, monkeypatch
):
    default_path = isolated_config / "default.json"
    monkeypatch.setattr(config, "DEFAULT_JSON_PATH", default_path)
    monkeypatch.setenv("JSON_PATH", "")

    path = config.get_json_path()

    assert path == Path("")
    assert path != default_path


def test_build_service_uses_json_path_and_preserves_explicit_storage(
    isolated_config, monkeypatch
):
    selected_path = isolated_config / "selected.json"
    default_path = isolated_config / "default.json"
    monkeypatch.setattr(config, "DEFAULT_JSON_PATH", default_path)
    monkeypatch.setenv("JSON_PATH", str(selected_path))

    service = main_module.build_service()

    assert service.storage.path == selected_path
    assert not selected_path.exists()
    assert not default_path.exists()

    storage = MemoryStorage()
    monkeypatch.setenv("JSON_PATH", "")

    assert main_module.build_service(storage).storage is storage


def test_api_and_cli_use_json_path_from_env_file(isolated_config, monkeypatch):
    selected_path = isolated_config / "selected.json"
    default_path = isolated_config / "default.json"
    config.ENV_FILE.write_text(
        f"JSON_PATH={selected_path.as_posix()}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "DEFAULT_JSON_PATH", default_path)
    previous_service = app.state.planner

    try:
        app.state.planner = main_module.build_service()
        with TestClient(app, follow_redirects=False) as client:
            response = client.post(
                "/tasks",
                json={"title": "Изолированная задача", "priority": 2},
            )
            assert response.status_code == 201, response.text

        assert selected_path.exists()
        assert not default_path.exists()

        messages = []
        cli_service = main_module.build_service()
        execute_command(
            cli_service,
            "list",
            read=lambda _prompt: "",
            write=messages.append,
        )
        assert any("изолированная задача" in message.casefold() for message in messages)
    finally:
        app.state.planner = previous_service
