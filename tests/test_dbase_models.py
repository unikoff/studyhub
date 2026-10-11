import os
import subprocess
import sys

import pytest
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import IntegrityError

from app.DBase.init_db import initialize_database
from app.DBase.models import Base, TaskRow
from app.core.config import Settings


def _settings_for(database_path):
    database_url = URL.create(
        "sqlite", database=database_path.as_posix()
    ).render_as_string(hide_password=False)
    return Settings(
        app_name="Test",
        database_url=database_url,
    )


def test_task_row_registers_six_columns_and_database_constraints():
    table = TaskRow.__table__

    assert table.name == "tasks"
    assert list(table.columns.keys()) == [
        "id",
        "title",
        "priority",
        "is_done",
        "tags",
        "title_normalized",
    ]
    assert all(not column.nullable for column in table.columns)
    assert table.c.id.primary_key
    assert table.c.priority.default.arg == 2
    assert table.c.is_done.default.arg is False
    tags_default = table.c.tags.default.arg
    first_tags = tags_default(None)
    second_tags = tags_default(None)
    assert first_tags == []
    assert second_tags == []
    assert first_tags is not second_tags
    assert table.c.title.type.length is None
    assert {constraint.name for constraint in table.constraints} >= {
        "ck_tasks_id_positive",
        "ck_tasks_priority_range",
    }
    assert set(Base.metadata.tables) == {"tasks"}


def test_initialize_database_creates_expected_schema_and_is_repeatable(tmp_path):
    database_path = tmp_path / "planner.sqlite3"
    settings = _settings_for(database_path)

    assert not database_path.exists()
    initialize_database(settings)

    engine = create_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            columns = connection.execute(text("PRAGMA table_info(tasks)")).all()
            create_sql = connection.execute(
                text(
                    "SELECT sql FROM sqlite_master "
                    "WHERE type = :kind AND name = :name"
                ),
                {"kind": "table", "name": "tasks"},
            ).scalar_one()
            initial_schema = (columns, create_sql)

            assert [column[1] for column in columns] == [
                "id",
                "title",
                "priority",
                "is_done",
                "tags",
                "title_normalized",
            ]
            assert "ck_tasks_id_positive" in create_sql
            assert "ck_tasks_priority_range" in create_sql
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO tasks "
                        "(id, title, priority, is_done, tags, title_normalized) "
                        "VALUES (0, 'bad id', 2, 0, '[]', 'bad id')"
                    )
                )
            connection.rollback()
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO tasks "
                        "(id, title, priority, is_done, tags, title_normalized) "
                        "VALUES (1, 'bad priority', 6, 0, '[]', 'bad priority')"
                    )
                )
            connection.rollback()

        initialize_database(settings)

        with engine.connect() as connection:
            repeated_schema = (
                connection.execute(text("PRAGMA table_info(tasks)")).all(),
                connection.execute(
                    text(
                        "SELECT sql FROM sqlite_master "
                        "WHERE type = :kind AND name = :name"
                    ),
                    {"kind": "table", "name": "tasks"},
                ).scalar_one(),
            )
            assert repeated_schema == initial_schema
            assert connection.execute(
                text("SELECT count(*) FROM tasks")
            ).scalar_one() == 0
    finally:
        engine.dispose()


def test_importing_init_db_does_not_create_a_database_file(tmp_path):
    database_path = tmp_path / "import-only.sqlite3"
    settings = _settings_for(database_path)
    environment = os.environ.copy()
    environment["DATABASE_URL"] = settings.database_url

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.api; import app.DBase.engine; import app.DBase.init_db",
        ],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not database_path.exists()


def test_init_db_module_creates_schema_for_configured_database(tmp_path):
    database_path = tmp_path / "module-run.sqlite3"
    settings = _settings_for(database_path)
    environment = os.environ.copy()
    environment["DATABASE_URL"] = settings.database_url

    result = subprocess.run(
        [sys.executable, "-m", "app.DBase.init_db"],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert database_path.exists()
    engine = create_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'tasks'"
                )
            ).scalar_one() == "tasks"
    finally:
        engine.dispose()
