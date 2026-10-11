import os
import subprocess
import sys

from sqlalchemy import URL, func, inspect, select

from app.DBase.engine import make_engine
from app.DBase.init_db import initialize_database
from app.DBase.models import TaskRow
from app.DBase.session import make_session_factory
from app.core.config import Settings


def _settings_for(database_path):
    database_url = URL.create(
        "sqlite", database=database_path.as_posix()
    ).render_as_string(hide_password=False)
    return Settings(
        json_path=database_path.parent / "tasks.json",
        app_name="Test",
        database_url=database_url,
    )


def test_factory_creates_fresh_sessions_without_connecting(tmp_path):
    database_path = tmp_path / "factory.sqlite3"
    settings = _settings_for(database_path)
    engine = make_engine(settings.database_url)
    try:
        factory = make_session_factory(engine)
        first = factory()
        second = factory()
        try:
            assert first is not second
            assert first.bind is engine
            assert second.bind is engine
            assert not database_path.exists()
        finally:
            first.close()
            second.close()
    finally:
        engine.dispose()


def test_initialize_database_creates_missing_parent_directory(tmp_path):
    database_path = tmp_path / "new-data" / "nested" / "studyhub.sqlite3"
    settings = _settings_for(database_path)

    assert not database_path.parent.exists()
    initialize_database(settings)

    assert database_path.is_file()
    engine = make_engine(settings.database_url)
    try:
        assert inspect(engine).has_table("tasks")
    finally:
        engine.dispose()


def test_task_rows_flush_commit_refresh_and_read_in_new_session(tmp_path):
    database_path = tmp_path / "session-workflow.sqlite3"
    settings = _settings_for(database_path)
    initialize_database(settings)
    engine = make_engine(settings.database_url)
    factory = make_session_factory(engine)

    try:
        with factory() as session:
            first_row = TaskRow(
                title="Первая задача",
                priority=4,
                title_normalized="первая задача",
            )
            session.add(first_row)
            assert first_row.id is None

            session.flush()
            assert type(first_row.id) is int
            first_id = first_row.id
            assert session.scalar(select(func.count()).select_from(TaskRow)) == 1

            session.commit()
            session.refresh(first_row)
            assert first_row.title == "Первая задача"
            assert first_row.priority == 4
            assert first_row.is_done is False
            assert first_row.tags == []
            assert first_row.title_normalized == "первая задача"

            second_row = TaskRow(
                title="Вторая задача",
                priority=2,
                title_normalized="вторая задача",
            )
            session.add(second_row)
            session.flush()
            assert type(second_row.id) is int
            second_id = second_row.id
            assert session.scalar(select(func.count()).select_from(TaskRow)) == 2

            session.commit()
            session.refresh(second_row)
            assert second_row.tags == []

        with factory() as new_session:
            saved_first = new_session.get(TaskRow, first_id)
            saved_second = new_session.get(TaskRow, second_id)

            assert saved_first is not None
            assert saved_second is not None
            assert (
                saved_first.id,
                saved_first.title,
                saved_first.priority,
                saved_first.is_done,
                saved_first.tags,
                saved_first.title_normalized,
            ) == (
                first_id,
                "Первая задача",
                4,
                False,
                [],
                "первая задача",
            )
            assert saved_second.title == "Вторая задача"
            assert saved_second.priority == 2
            assert saved_second.is_done is False
            assert saved_second.tags == []
            assert saved_second.title_normalized == "вторая задача"
            assert saved_first.tags is not saved_second.tags
    finally:
        engine.dispose()


def test_importing_session_factory_module_has_no_database_side_effect(tmp_path):
    database_path = tmp_path / "import-only.sqlite3"
    settings = _settings_for(database_path)
    environment = os.environ.copy()
    environment["DATABASE_URL"] = settings.database_url

    result = subprocess.run(
        [sys.executable, "-c", "import app.DBase.session"],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not database_path.exists()
