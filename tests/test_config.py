from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL, make_url

from app import main as main_module
from app.api import app
from app.cli import run
from app.core import config
from app.DBase.engine import make_engine
from app.DBase.init_db import initialize_database
from app.DBase.session import make_session_factory
from app.main import sql_service_context


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    return tmp_path


def test_load_settings_uses_defaults_when_values_are_absent(isolated_config):
    settings = config.load_settings(environ={}, project_root=isolated_config)

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


def test_api_and_cli_share_loaded_settings_and_sql(isolated_config):
    config.ENV_FILE.write_text(
        "APP_NAME=StudyHub Test\n",
        encoding="utf-8",
    )
    settings = config.load_settings(project_root=isolated_config)
    Path(make_url(settings.database_url).database).parent.mkdir(parents=True)
    initialize_database(settings)
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    previous_settings = app.state.settings
    previous_factory = app.state.session_factory

    try:
        app.state.settings = settings
        app.state.session_factory = session_factory
        with TestClient(app, follow_redirects=False) as client:
            response = client.post(
                "/tasks",
                json={"title": "Изолированная задача", "priority": 2},
            )
            assert response.status_code == 201, response.text

        messages = []
        answers = iter(("find", str(response.json()["id"]), "stats", "exit"))
        run(
            lambda: sql_service_context(session_factory),
            read=lambda _prompt: next(answers),
            write=messages.append,
        )
        assert any("изолированная задача" in message.casefold() for message in messages)
        assert any("Всего: 1" in message for message in messages)
    finally:
        app.state.settings = previous_settings
        app.state.session_factory = previous_factory
        engine.dispose()


def test_cli_main_uses_configured_sqlite(isolated_config, monkeypatch):
    settings = config.Settings(
        app_name="StudyHub Test",
        database_url=config.default_database_url(isolated_config),
    )
    Path(make_url(settings.database_url).database).parent.mkdir(parents=True)
    initialize_database(settings)
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    try:
        with sql_service_context(session_factory) as planner:
            planner.add_task("Задача из SQL", 2)
    finally:
        engine.dispose()

    monkeypatch.setattr(main_module, "load_settings", lambda: settings)
    messages = []

    def run_cli(service_context):
        answers = iter(("list", "exit"))
        return run(
            service_context,
            read=lambda _prompt: next(answers),
            write=messages.append,
        )

    monkeypatch.setattr(main_module, "run", run_cli)
    main_module.main()

    assert any("Задача из SQL" in message for message in messages)
