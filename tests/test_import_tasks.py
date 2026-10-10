import json

import pytest
from sqlalchemy import URL, inspect, select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.DBase.engine import make_engine
from app.DBase.import_tasks import (
    SnapshotImportError,
    import_snapshot,
    main,
)
from app.DBase.init_db import initialize_database
from app.DBase.models import TaskRow
from app.DBase.session import make_session_factory
from app.core.config import Settings
from app.main import build_service
from app.storage import JsonStorage


@pytest.fixture
def import_database(tmp_path):
    database_path = tmp_path / "import.sqlite3"
    database_url = URL.create(
        "sqlite", database=database_path.as_posix()
    ).render_as_string(hide_password=False)
    settings = Settings(
        json_path=tmp_path / "tasks.json",
        app_name="Test",
        database_url=database_url,
    )
    initialize_database(settings)
    engine = make_engine(database_url)
    try:
        yield engine, database_url, make_session_factory(engine)
    finally:
        engine.dispose()


def write_snapshot(path, records):
    path.write_text(
        json.dumps(records, ensure_ascii=False), encoding="utf-8"
    )


def test_cli_imports_old_and_current_records_and_keeps_json_usable(
    tmp_path, import_database, capsys
):
    _engine, database_url, session_factory = import_database
    source = tmp_path / "source.json"
    write_snapshot(
        source,
        [
            {
                "id": 5,
                "title": "Старая задача",
                "priority": 4,
                "is_done": True,
            },
            {
                "id": 9,
                "title": "Новая задача",
                "priority": 2,
                "is_done": False,
                "tags": ["sql", "готово"],
            },
        ],
    )
    before = source.read_bytes()

    assert main(
        ["--source", str(source), "--database-url", database_url]
    ) == 0

    assert capsys.readouterr().out == "Импортировано задач: 2\n"
    assert source.read_bytes() == before
    with session_factory() as session:
        rows = session.scalars(select(TaskRow).order_by(TaskRow.id)).all()
        assert [
            (
                row.id,
                row.title,
                row.priority,
                row.is_done,
                row.tags,
                row.title_normalized,
            )
            for row in rows
        ] == [
            (5, "Старая задача", 4, True, [], "старая задача"),
            (9, "Новая задача", 2, False, ["sql", "готово"], "новая задача"),
        ]

    json_planner = build_service(JsonStorage(source))
    assert [task.id for task in json_planner.list_tasks()] == [5, 9]


def test_empty_list_is_a_valid_snapshot(tmp_path, import_database):
    _engine, database_url, session_factory = import_database
    source = tmp_path / "empty.json"
    write_snapshot(source, [])

    assert import_snapshot(source, database_url) == 0
    with session_factory() as session:
        assert session.scalars(select(TaskRow)).all() == []


@pytest.mark.parametrize(
    "records",
    [
        {"id": 1},
        [
            {
                "id": 1,
                "title": "valid",
                "priority": 2,
                "is_done": False,
            },
            {"id": 2, "title": "late row is invalid"},
        ],
        [
            {"id": 1, "title": "same", "priority": 2, "is_done": False},
            {"id": 1, "title": "same", "priority": 2, "is_done": False},
        ],
        [{"id": 1, "title": " padded ", "priority": 2, "is_done": False}],
        [
            {
                "id": 1,
                "title": "valid",
                "priority": 2,
                "is_done": False,
                "tags": [" padded "],
            }
        ],
        [
            {
                "id": 1,
                "title": "valid",
                "priority": 2,
                "is_done": False,
                "tags": [],
                "unexpected": True,
            }
        ],
    ],
)
def test_invalid_snapshot_fails_before_writing_target(
    tmp_path, import_database, records
):
    _engine, database_url, session_factory = import_database
    source = tmp_path / "invalid.json"
    write_snapshot(source, records)
    before = source.read_bytes()

    with pytest.raises(SnapshotImportError):
        import_snapshot(source, database_url)

    assert source.read_bytes() == before
    with session_factory() as session:
        assert session.scalar(select(TaskRow.id).limit(1)) is None


def test_invalid_json_and_missing_source_are_errors(tmp_path, import_database):
    _engine, database_url, _session_factory = import_database
    source = tmp_path / "broken.json"
    source.write_text("{", encoding="utf-8")

    with pytest.raises(SnapshotImportError, match="Некорректный JSON"):
        import_snapshot(source, database_url)
    with pytest.raises(SnapshotImportError, match="Не удалось прочитать"):
        import_snapshot(tmp_path / "missing.json", database_url)

    source.write_bytes(b"\xff")
    with pytest.raises(SnapshotImportError, match="Не удалось прочитать"):
        import_snapshot(source, database_url)


def test_nonempty_target_is_refused_without_changing_existing_row(
    tmp_path, import_database
):
    _engine, database_url, session_factory = import_database
    source = tmp_path / "source.json"
    write_snapshot(
        source,
        [{"id": 2, "title": "incoming", "priority": 3, "is_done": False}],
    )
    with session_factory() as session:
        session.add(
            TaskRow(
                id=1,
                title="existing",
                priority=1,
                is_done=True,
                tags=["keep"],
                title_normalized="existing",
            )
        )
        session.commit()

    with pytest.raises(SnapshotImportError, match="не пуста"):
        import_snapshot(source, database_url)

    with session_factory() as session:
        row = session.get(TaskRow, 1)
        assert (row.title, row.priority, row.is_done, row.tags) == (
            "existing",
            1,
            True,
            ["keep"],
        )
        assert session.get(TaskRow, 2) is None


def test_late_database_failure_rolls_back_all_rows(tmp_path, import_database):
    engine, database_url, session_factory = import_database
    source = tmp_path / "source.json"
    write_snapshot(
        source,
        [
            {"id": 1, "title": "first", "priority": 2, "is_done": False},
            {"id": 2, "title": "last", "priority": 3, "is_done": False},
        ],
    )
    before = source.read_bytes()
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER reject_last_task BEFORE INSERT ON tasks "
            "WHEN NEW.id = 2 BEGIN SELECT RAISE(ABORT, 'rejected'); END"
        )

    with pytest.raises(IntegrityError):
        import_snapshot(source, database_url)

    with session_factory() as session:
        assert session.scalars(select(TaskRow.id)).all() == []
    assert source.read_bytes() == before


def test_import_does_not_create_the_schema(tmp_path):
    database_path = tmp_path / "unprepared.sqlite3"
    database_url = URL.create(
        "sqlite", database=database_path.as_posix()
    ).render_as_string(hide_password=False)
    source = tmp_path / "source.json"
    write_snapshot(
        source,
        [{"id": 1, "title": "valid", "priority": 2, "is_done": False}],
    )

    with pytest.raises(OperationalError):
        import_snapshot(source, database_url)

    engine = make_engine(database_url)
    try:
        assert "tasks" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()
