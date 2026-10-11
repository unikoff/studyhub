from contextlib import contextmanager
import os
import subprocess
import sys
import json
from pathlib import Path
import shutil

import pytest
from fastapi import Depends
from sqlalchemy import URL, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.api import app
from app.cli import run
from app.core.dependencies import get_db, get_planner
from app.errors import TaskNotFoundError
from app.DBase.engine import make_engine
from app.DBase.init_db import initialize_database
from app.DBase.import_tasks import import_snapshot
from app.DBase.models import TaskRow
from app.DBase.session import make_session_factory
from app.core.config import Settings
from app.main import build_service, sql_service_context
from app.models import Task
from app.DBase.repositories import SqlTaskRepository


@pytest.fixture
def sql_database(tmp_path):
    database_path = tmp_path / "planner.sqlite3"
    database_url = URL.create(
        "sqlite", database=database_path.as_posix()
    ).render_as_string(hide_password=False)
    settings = Settings(
        app_name="Test",
        database_url=database_url,
    )
    initialize_database(settings)
    engine = make_engine(database_url)
    try:
        yield engine, make_session_factory(engine)
    finally:
        engine.dispose()


def test_sql_repository_reads_empty_list_and_returns_none(sql_database):
    _engine, session_factory = sql_database
    with session_factory() as session:
        repository = SqlTaskRepository(session)

        assert repository.list() == []
        assert repository.get(999) is None
        assert repository.session is session
        assert session.scalar(select(TaskRow.id).limit(1)) is None


def test_sql_repository_maps_ordered_rows_and_get_to_tasks_after_close(
    sql_database,
):
    engine, session_factory = sql_database
    with session_factory() as session:
        session.add_all(
            [
                TaskRow(
                    id=8,
                    title="Later row",
                    priority=4,
                    tags=["sql", "reading"],
                    title_normalized="later row",
                ),
                TaskRow(
                    id=2,
                    title="First row",
                    priority=2,
                    is_done=True,
                    tags=["review"],
                    title_normalized="first row",
                ),
            ]
        )
        session.commit()

    commits = []

    def on_commit(_connection):
        commits.append(True)

    event.listen(engine, "commit", on_commit)
    try:
        with session_factory() as session:
            repository = SqlTaskRepository(session)
            tasks = repository.list()
            existing = repository.get(8)
            missing = repository.get(999)

            session_rows = session.scalars(
                select(TaskRow).order_by(TaskRow.id)
            ).all()
            assert [row.id for row in session_rows] == [2, 8]
            assert commits == []
    finally:
        event.remove(engine, "commit", on_commit)

    assert [task.id for task in tasks] == [2, 8]
    assert all(isinstance(task, Task) for task in tasks)
    expected = [
        Task(2, "First row", 2, is_done=True, tags=["review"]),
        Task(8, "Later row", 4, tags=["sql", "reading"]),
    ]
    assert tasks == expected
    assert existing == tasks[1]
    assert missing is None

    tasks[1].tags.append("local-only")
    assert tasks[0].tags == ["review"]

    with session_factory() as verification_session:
        rows = verification_session.scalars(
            select(TaskRow).order_by(TaskRow.id)
        ).all()
        assert [row.tags for row in rows] == [["review"], ["sql", "reading"]]


def test_sql_get_provider_uses_a_request_session(
    sql_database, api_client, api_service
):
    engine, _session_factory = sql_database
    with _session_factory() as session:
        session.add(
            TaskRow(
                id=7,
                title="SQL task",
                priority=3,
                tags=["internal"],
                title_normalized="sql task",
            )
        )
        session.commit()

    created_sessions = []

    class TrackedSession(Session):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.was_closed = False
            created_sessions.append(self)

        def close(self):
            self.was_closed = True
            super().close()

    tracked_factory = sessionmaker(bind=engine, class_=TrackedSession)
    previous_factory = getattr(app.state, "session_factory", None)
    had_factory = hasattr(app.state, "session_factory")
    previous_overrides = app.dependency_overrides.copy()

    def get_sql_planner(db=Depends(get_db)):
        return build_service(
            repository=SqlTaskRepository(db),
            write_scope=db.begin,
        )

    app.state.session_factory = tracked_factory
    app.dependency_overrides[get_planner] = get_sql_planner
    try:
        found = api_client.get("/tasks/7")
        missing = api_client.get("/tasks/999")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        if had_factory:
            app.state.session_factory = previous_factory
        else:
            del app.state.session_factory

    assert found.status_code == 200
    assert found.json() == {
        "id": 7,
        "title": "SQL task",
        "priority": 3,
        "is_done": False,
    }
    assert "tags" not in found.json()
    assert missing.status_code == 404
    assert len(created_sessions) == 2
    assert all(session.was_closed for session in created_sessions)


def test_sql_service_context_closes_session_after_success_and_error(sql_database):
    engine, _session_factory = sql_database
    with _session_factory() as session:
        session.add(
            TaskRow(
                id=10,
                title="CLI SQL task",
                priority=2,
                tags=[],
                title_normalized="cli sql task",
            )
        )
        session.commit()

    class TrackedSession(Session):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.was_closed = False

        def close(self):
            self.was_closed = True
            super().close()

    tracked_factory = sessionmaker(bind=engine, class_=TrackedSession)
    created = []

    def make_session():
        session = tracked_factory()
        created.append(session)
        return session

    with sql_service_context(make_session) as planner:
        assert planner.get_task(10).title == "CLI SQL task"
    assert created[-1].was_closed

    with pytest.raises(RuntimeError, match="command failed"):
        with sql_service_context(make_session):
            raise RuntimeError("command failed")
    assert created[-1].was_closed


def test_sql_post_uses_generated_id_and_sql_provider(
    sql_database, api_client, api_service
):
    engine, session_factory = sql_database
    with session_factory() as session:
        session.add(
            TaskRow(
                id=40,
                title="Imported task",
                priority=4,
                is_done=True,
                tags=["history"],
                title_normalized="imported task",
            )
        )
        session.commit()

    previous_factory = getattr(app.state, "session_factory", None)
    had_factory = hasattr(app.state, "session_factory")
    previous_overrides = app.dependency_overrides.copy()

    def get_sql_planner(db=Depends(get_db)):
        return build_service(
            repository=SqlTaskRepository(db),
            write_scope=db.begin,
        )

    app.state.session_factory = session_factory
    app.dependency_overrides[get_planner] = get_sql_planner
    try:
        response = api_client.post(
            "/tasks", json={"title": "New SQL task", "priority": 3}
        )
        invalid = api_client.post("/tasks", json={"title": "   ", "priority": 2})
        missing_priority = api_client.post(
            "/tasks", json={"title": "No priority"}
        )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        if had_factory:
            app.state.session_factory = previous_factory
        else:
            del app.state.session_factory

    assert response.status_code == 201
    public_data = response.json()
    assert set(public_data) == {"id", "title", "priority", "is_done"}
    assert public_data["id"] > 40
    assert public_data["title"] == "New SQL task"
    assert public_data["priority"] == 3
    assert public_data["is_done"] is False
    assert invalid.status_code == 422
    assert missing_priority.status_code == 422
    with session_factory() as session:
        created = session.get(TaskRow, public_data["id"])
        assert created is not None
        assert (
            created.title,
            created.priority,
            created.is_done,
            created.tags,
            created.title_normalized,
        ) == ("New SQL task", 3, False, [], "new sql task")
        assert session.get(TaskRow, 40).tags == ["history"]

    follow_up = api_client.post(
        "/tasks", json={"title": "Follow-up SQL task", "priority": 2}
    )
    assert follow_up.status_code == 201
    assert follow_up.json()["id"] == 42
    assert api_service.get_task(42).title == "Follow-up SQL task"


def test_sql_create_service_validates_and_copies_tags(sql_database):
    engine, session_factory = sql_database
    input_tags = [" sql ", " student "]
    with session_factory() as session:
        planner = build_service(
            repository=SqlTaskRepository(session),
            write_scope=session.begin,
        )
        created = planner.add_task("  Tagged task  ", 2, tags=input_tags)

    input_tags.append("outside")
    assert created.id > 0
    assert created.title == "Tagged task"
    assert created.tags == ["sql", "student"]

    with session_factory() as session:
        row = session.get(TaskRow, created.id)
        assert row.tags == ["sql", "student"]
        assert row.title_normalized == "tagged task"

    statements = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        with session_factory() as session:
            planner = build_service(
                repository=SqlTaskRepository(session),
                write_scope=session.begin,
            )
            invalid_inputs = [
                ("   ", 2, None),
                ("Valid", 6, None),
                ("Valid", 2, [""]),
            ]
            for title, priority, tags in invalid_inputs:
                with pytest.raises(ValueError):
                    planner.add_task(title, priority, tags)
                assert session.get_transaction() is None
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)
    assert statements == []


def test_sql_create_rolls_back_when_insert_fails(sql_database):
    engine, _session_factory = sql_database
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER reject_new_task BEFORE INSERT ON tasks "
            "WHEN NEW.title = 'Rejected' "
            "BEGIN SELECT RAISE(ABORT, 'rejected'); END"
        )

    factory = make_session_factory(engine)
    with factory() as session:
        planner = build_service(
            repository=SqlTaskRepository(session),
            write_scope=session.begin,
        )
        with pytest.raises(IntegrityError):
            planner.add_task("Rejected", 2)

    with factory() as session:
        assert session.scalars(select(TaskRow)).all() == []


def test_sql_put_preserves_internal_fields_and_uses_sql_provider(
    sql_database, api_client, api_service
):
    _engine, session_factory = sql_database
    with session_factory() as session:
        session.add_all(
            [
                TaskRow(
                    id=51,
                    title="Old title",
                    priority=2,
                    is_done=True,
                    tags=["keep", "private"],
                    title_normalized="old title",
                ),
                TaskRow(
                    id=52,
                    title="Neighbor",
                    priority=4,
                    tags=["neighbor"],
                    title_normalized="neighbor",
                ),
            ]
        )
        session.commit()

    previous_factory = getattr(app.state, "session_factory", None)
    had_factory = hasattr(app.state, "session_factory")
    previous_overrides = app.dependency_overrides.copy()

    def get_sql_planner(db=Depends(get_db)):
        return build_service(
            repository=SqlTaskRepository(db),
            write_scope=db.begin,
        )

    app.state.session_factory = session_factory
    app.dependency_overrides[get_planner] = get_sql_planner
    try:
        response = api_client.put(
            "/tasks/51",
            json={"title": "  New title  ", "priority": 5, "is_done": False},
        )
        missing = api_client.put(
            "/tasks/999", json={"title": "Missing", "priority": 1, "is_done": False}
        )
        invalid = api_client.put(
            "/tasks/51", json={"title": "   ", "priority": 1, "is_done": False}
        )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        if had_factory:
            app.state.session_factory = previous_factory
        else:
            del app.state.session_factory

    assert response.status_code == 200
    assert response.json() == {
        "id": 51,
        "title": "New title",
        "priority": 5,
        "is_done": False,
    }
    assert "tags" not in response.json()
    assert missing.status_code == 404
    assert invalid.status_code == 422

    with session_factory() as session:
        changed = session.get(TaskRow, 51)
        neighbor = session.get(TaskRow, 52)
        assert (
            changed.id,
            changed.title,
            changed.priority,
            changed.is_done,
            changed.tags,
            changed.title_normalized,
        ) == (51, "New title", 5, False, ["keep", "private"], "new title")
        assert (
            neighbor.id,
            neighbor.title,
            neighbor.priority,
            neighbor.is_done,
            neighbor.tags,
            neighbor.title_normalized,
        ) == (52, "Neighbor", 4, False, ["neighbor"], "neighbor")

    sql_task = api_service.add_task("SQL before PUT", 2, tags=["keep"])
    sql_response = api_client.put(
        f"/tasks/{sql_task.id}",
        json={"title": "SQL after PUT", "priority": 3, "is_done": False},
    )
    assert sql_response.status_code == 200
    assert sql_response.json()["title"] == "SQL after PUT"
    assert api_service.get_task(sql_task.id).tags == ["keep"]


def test_sql_put_validates_before_update_and_rolls_back_write_failure(
    sql_database,
):
    engine, session_factory = sql_database
    with session_factory() as session:
        session.add(
            TaskRow(
                id=61,
                title="Original",
                priority=3,
                tags=["keep"],
                title_normalized="original",
            )
        )
        session.commit()

    statements = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.lstrip().split(None, 1)[0].upper())

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        with session_factory() as session:
            planner = build_service(
                repository=SqlTaskRepository(session),
                write_scope=session.begin,
            )
            with pytest.raises(ValueError):
                planner.replace_task(
                    61, title="Invalid", priority=3, is_done="false"
                )
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)
    assert "UPDATE" not in statements

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER reject_task_update BEFORE UPDATE ON tasks "
            "WHEN NEW.title = 'Rejected' "
            "BEGIN SELECT RAISE(ABORT, 'rejected'); END"
        )

    with session_factory() as session:
        planner = build_service(
            repository=SqlTaskRepository(session),
            write_scope=session.begin,
        )
        with pytest.raises(IntegrityError):
            planner.replace_task(
                61, title="Rejected", priority=1, is_done=True
            )

    with session_factory() as session:
        row = session.get(TaskRow, 61)
        assert (
            row.title,
            row.priority,
            row.is_done,
            row.tags,
            row.title_normalized,
        ) == ("Original", 3, False, ["keep"], "original")


def test_sql_patch_keeps_partial_contract_and_uses_sql_provider(
    sql_database, api_client, api_service
):
    engine, session_factory = sql_database
    with session_factory() as session:
        session.add_all(
            [
                TaskRow(
                    id=71,
                    title="Original title",
                    priority=4,
                    is_done=True,
                    tags=["private", "retain"],
                    title_normalized="original title",
                ),
                TaskRow(
                    id=72,
                    title="Neighbor",
                    priority=1,
                    tags=["neighbor"],
                    title_normalized="neighbor",
                ),
            ]
        )
        session.commit()

    previous_factory = getattr(app.state, "session_factory", None)
    had_factory = hasattr(app.state, "session_factory")
    previous_overrides = app.dependency_overrides.copy()

    def get_sql_planner(db=Depends(get_db)):
        return build_service(
            repository=SqlTaskRepository(db),
            write_scope=db.begin,
        )

    app.state.session_factory = session_factory
    app.dependency_overrides[get_planner] = get_sql_planner
    no_op_statements = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _many):
        no_op_statements.append(statement.lstrip().split(None, 1)[0].upper())

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        put = api_client.put(
            "/tasks/71",
            json={"title": "Before PATCH", "priority": 5, "is_done": True},
        )
        lowered = api_client.patch("/tasks/71", json={"is_done": False})
        no_op_start = len(no_op_statements)
        empty = api_client.patch("/tasks/71", json={})
        explicit_null = api_client.patch("/tasks/71", json={"title": None})
        unknown_empty = api_client.patch("/tasks/999", json={})
        no_op_end = len(no_op_statements)
        changed_fields = api_client.patch(
            "/tasks/71", json={"title": "Changed by PATCH", "priority": 2}
        )
        invalid = api_client.patch("/tasks/71", json={"title": "   "})
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        if had_factory:
            app.state.session_factory = previous_factory
        else:
            del app.state.session_factory

    assert put.status_code == lowered.status_code == changed_fields.status_code == 200
    assert lowered.json() == {
        "id": 71,
        "title": "Before PATCH",
        "priority": 5,
        "is_done": False,
    }
    assert empty.status_code == explicit_null.status_code == 200
    assert empty.json() == explicit_null.json() == lowered.json()
    assert unknown_empty.status_code == 404
    assert invalid.status_code == 422
    assert changed_fields.json() == {
        "id": 71,
        "title": "Changed by PATCH",
        "priority": 2,
        "is_done": False,
    }
    assert "UPDATE" not in no_op_statements[no_op_start:no_op_end]

    with session_factory() as session:
        changed = session.get(TaskRow, 71)
        neighbor = session.get(TaskRow, 72)
        assert (
            changed.id,
            changed.title,
            changed.priority,
            changed.is_done,
            changed.tags,
            changed.title_normalized,
        ) == (
            71,
            "Changed by PATCH",
            2,
            False,
            ["private", "retain"],
            "changed by patch",
        )
        assert (
            neighbor.title,
            neighbor.priority,
            neighbor.tags,
            neighbor.title_normalized,
        ) == ("Neighbor", 1, ["neighbor"], "neighbor")

    sql_task = api_service.add_task("SQL before PATCH", 2, tags=["keep"])
    sql_response = api_client.patch(
        f"/tasks/{sql_task.id}", json={"is_done": False}
    )
    assert sql_response.status_code == 200
    assert sql_response.json()["is_done"] is False
    assert api_service.get_task(sql_task.id).tags == ["keep"]


def test_sql_patch_validates_before_update_and_rolls_back_write_failure(
    sql_database,
):
    engine, session_factory = sql_database
    with session_factory() as session:
        session.add(
            TaskRow(
                id=81,
                title="Original",
                priority=3,
                is_done=True,
                tags=["keep"],
                title_normalized="original",
            )
        )
        session.commit()

    statements = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.lstrip().split(None, 1)[0].upper())

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        with session_factory() as session:
            planner = build_service(
                repository=SqlTaskRepository(session),
                write_scope=session.begin,
            )
            with pytest.raises(ValueError):
                planner.patch_task(81, title="   ", is_done=False)
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)
    assert "UPDATE" not in statements

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER reject_task_patch BEFORE UPDATE ON tasks "
            "WHEN NEW.title = 'Rejected' "
            "BEGIN SELECT RAISE(ABORT, 'rejected'); END"
        )

    with session_factory() as session:
        planner = build_service(
            repository=SqlTaskRepository(session),
            write_scope=session.begin,
        )
        with pytest.raises(IntegrityError):
            planner.patch_task(81, title="Rejected", is_done=False)

    with session_factory() as session:
        row = session.get(TaskRow, 81)
        assert (
            row.title,
            row.priority,
            row.is_done,
            row.tags,
            row.title_normalized,
        ) == ("Original", 3, True, ["keep"], "original")


def test_sql_mark_done_is_idempotent_and_preserves_other_fields(sql_database):
    engine, session_factory = sql_database
    with session_factory() as session:
        session.add_all(
            [
                TaskRow(
                    id=91,
                    title="Finish lesson",
                    priority=4,
                    tags=["course", "internal"],
                    title_normalized="finish lesson",
                ),
                TaskRow(
                    id=92,
                    title="Neighbor",
                    priority=2,
                    tags=["neighbor"],
                    title_normalized="neighbor",
                ),
            ]
        )
        session.commit()

    updates = []

    def record_update(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("UPDATE"):
            updates.append(statement)

    event.listen(engine, "before_cursor_execute", record_update)
    try:
        with session_factory() as session:
            planner = build_service(
                repository=SqlTaskRepository(session),
                write_scope=session.begin,
            )
            first = planner.mark_done(91)
            second = planner.mark_done(91)
            with pytest.raises(TaskNotFoundError):
                planner.mark_done(999)
    finally:
        event.remove(engine, "before_cursor_execute", record_update)

    assert first == second == Task(
        91,
        "Finish lesson",
        4,
        is_done=True,
        tags=["course", "internal"],
    )
    assert len(updates) == 1

    with session_factory() as session:
        done = session.get(TaskRow, 91)
        neighbor = session.get(TaskRow, 92)
        assert (
            done.id,
            done.title,
            done.priority,
            done.is_done,
            done.tags,
            done.title_normalized,
        ) == (91, "Finish lesson", 4, True, ["course", "internal"], "finish lesson")
        assert (
            neighbor.title,
            neighbor.priority,
            neighbor.is_done,
            neighbor.tags,
            neighbor.title_normalized,
        ) == ("Neighbor", 2, False, ["neighbor"], "neighbor")


def test_sql_delete_endpoint_removes_only_target_and_uses_sql_provider(
    sql_database, api_client, api_service
):
    _engine, session_factory = sql_database
    with session_factory() as session:
        session.add_all(
            [
                TaskRow(
                    id=101,
                    title="Remove me",
                    priority=3,
                    tags=["target"],
                    title_normalized="remove me",
                ),
                TaskRow(
                    id=102,
                    title="Keep me",
                    priority=5,
                    tags=["neighbor"],
                    title_normalized="keep me",
                ),
            ]
        )
        session.commit()

    previous_factory = getattr(app.state, "session_factory", None)
    had_factory = hasattr(app.state, "session_factory")
    previous_overrides = app.dependency_overrides.copy()

    def get_sql_planner(db=Depends(get_db)):
        return build_service(
            repository=SqlTaskRepository(db),
            write_scope=db.begin,
        )

    app.state.session_factory = session_factory
    app.dependency_overrides[get_planner] = get_sql_planner
    try:
        deleted = api_client.delete("/tasks/101")
        missing_get = api_client.get("/tasks/101")
        repeated_delete = api_client.delete("/tasks/101")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        if had_factory:
            app.state.session_factory = previous_factory
        else:
            del app.state.session_factory

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert missing_get.status_code == repeated_delete.status_code == 404
    with session_factory() as session:
        assert session.get(TaskRow, 101) is None
        neighbor = session.get(TaskRow, 102)
        assert (
            neighbor.title,
            neighbor.priority,
            neighbor.tags,
            neighbor.title_normalized,
        ) == ("Keep me", 5, ["neighbor"], "keep me")

    sql_task = api_service.add_task("SQL delete", 1)
    sql_delete = api_client.delete(f"/tasks/{sql_task.id}")
    assert sql_delete.status_code == 204
    with pytest.raises(TaskNotFoundError):
        api_service.get_task(sql_task.id)


def test_sql_delete_rolls_back_when_database_rejects_delete(sql_database):
    engine, session_factory = sql_database
    with session_factory() as session:
        session.add_all(
            [
                TaskRow(
                    id=111,
                    title="Protected row",
                    priority=2,
                    tags=["keep"],
                    title_normalized="protected row",
                ),
                TaskRow(
                    id=112,
                    title="Neighbor",
                    priority=1,
                    tags=["neighbor"],
                    title_normalized="neighbor",
                ),
            ]
        )
        session.commit()

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER reject_task_delete BEFORE DELETE ON tasks "
            "WHEN OLD.id = 111 "
            "BEGIN SELECT RAISE(ABORT, 'rejected'); END"
        )

    with session_factory() as session:
        planner = build_service(
            repository=SqlTaskRepository(session),
            write_scope=session.begin,
        )
        with pytest.raises(IntegrityError):
            planner.delete_task(111)

    with session_factory() as session:
        protected = session.get(TaskRow, 111)
        neighbor = session.get(TaskRow, 112)
        assert (
            protected.title,
            protected.priority,
            protected.is_done,
            protected.tags,
            protected.title_normalized,
        ) == ("Protected row", 2, False, ["keep"], "protected row")
        assert neighbor.title == "Neighbor"


def test_sql_select_filters_orders_and_limits_after_filter(sql_database):
    _engine, session_factory = sql_database
    with session_factory() as session:
        session.add_all(
            [
                TaskRow(
                    id=8, title="Open 8", priority=2,
                    tags=[], title_normalized="open 8",
                ),
                TaskRow(
                    id=2, title="Done 2", priority=3, is_done=True,
                    tags=[], title_normalized="done 2",
                ),
                TaskRow(
                    id=5, title="Open 5", priority=4,
                    tags=[], title_normalized="open 5",
                ),
                TaskRow(
                    id=3, title="Done 3", priority=1, is_done=True,
                    tags=[], title_normalized="done 3",
                ),
            ]
        )
        session.commit()

    with session_factory() as session:
        repository = SqlTaskRepository(session)
        assert [task.id for task in repository.select()] == [2, 3, 5, 8]
        assert [task.id for task in repository.select(is_done=False)] == [5, 8]
        assert [task.id for task in repository.select(is_done=True)] == [2, 3]
        assert [task.id for task in repository.select(sort_desc=True)] == [8, 5, 3, 2]
        assert [task.id for task in repository.select(
            is_done=False, sort_desc=True, limit=1
        )] == [8]
        assert [task.id for task in repository.select(limit=2)] == [2, 3]
        assert all(isinstance(task, Task) for task in repository.select())


def test_sql_statistics_uses_counts_for_empty_and_mixed_rows(sql_database):
    engine, session_factory = sql_database
    with session_factory() as session:
        repository = SqlTaskRepository(session)
        assert repository.statistics() == {"all": 0, "open": 0, "done": 0}

    with session_factory() as session:
        session.add_all(
            [
                TaskRow(
                    id=1, title="Open one", priority=2,
                    tags=[], title_normalized="open one",
                ),
                TaskRow(
                    id=2, title="Done one", priority=4, is_done=True,
                    tags=[], title_normalized="done one",
                ),
                TaskRow(
                    id=3, title="Open two", priority=1,
                    tags=[], title_normalized="open two",
                ),
            ]
        )
        session.commit()

    statements = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        with session_factory() as session:
            result = SqlTaskRepository(session).statistics()
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)

    assert result == {"all": 3, "open": 2, "done": 1}
    assert len(statements) == 1
    assert "COUNT" in statements[0].upper()


def test_sql_selection_and_statistics_endpoints_keep_api_contract(
    sql_database, api_client, api_service
):
    _engine, session_factory = sql_database
    with session_factory() as session:
        session.add_all(
            [
                TaskRow(
                    id=1,
                    title="Done one",
                    priority=3,
                    is_done=True,
                    tags=["private"],
                    title_normalized="done one",
                ),
                TaskRow(
                    id=2,
                    title="Open one",
                    priority=2,
                    tags=["internal"],
                    title_normalized="open one",
                ),
                TaskRow(
                    id=3,
                    title="Done two",
                    priority=5,
                    is_done=True,
                    tags=["private"],
                    title_normalized="done two",
                ),
            ]
        )
        session.commit()

    previous_factory = getattr(app.state, "session_factory", None)
    had_factory = hasattr(app.state, "session_factory")
    previous_overrides = app.dependency_overrides.copy()

    def get_sql_planner(db=Depends(get_db)):
        return build_service(
            repository=SqlTaskRepository(db),
            write_scope=db.begin,
        )

    app.state.session_factory = session_factory
    app.dependency_overrides[get_planner] = get_sql_planner
    try:
        default_list = api_client.get("/tasks")
        selected = api_client.get(
            "/tasks", params={"is_done": False, "sort_desc": True, "limit": 1}
        )
        invalid_limit = api_client.get("/tasks", params={"limit": 0})
        invalid_status = api_client.get("/tasks", params={"is_done": "maybe"})
        initial_stats = api_client.get("/stats")
        created = api_client.post(
            "/tasks", json={"title": "SQL-created", "priority": 2}
        )
        created_stats = api_client.get("/stats")
        with session_factory() as session:
            planner = build_service(
                repository=SqlTaskRepository(session),
                write_scope=session.begin,
            )
            planner.mark_done(created.json()["id"])
        done_stats = api_client.get("/stats")
        deleted = api_client.delete("/tasks/1")
        deleted_stats = api_client.get("/stats")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        if had_factory:
            app.state.session_factory = previous_factory
        else:
            del app.state.session_factory

    assert default_list.status_code == 200
    assert [task["id"] for task in default_list.json()] == [1, 2, 3]
    assert "tags" not in default_list.json()[0]
    assert selected.status_code == 200
    assert [task["id"] for task in selected.json()] == [2]
    assert invalid_limit.status_code == invalid_status.status_code == 422
    assert initial_stats.json() == {"total": 3, "open": 1, "done": 2}
    assert created.status_code == 201
    assert created_stats.json() == {"total": 4, "open": 2, "done": 2}
    assert done_stats.json() == {"total": 4, "open": 1, "done": 3}
    assert deleted.status_code == 204
    assert deleted_stats.json() == {"total": 3, "open": 1, "done": 2}

    with session_factory() as session:
        assert session.get(TaskRow, 1) is None
        created_row = session.get(TaskRow, created.json()["id"])
        assert created_row.is_done is True
        assert session.get(TaskRow, 2).is_done is False



def test_sql_search_matches_literal_search_behavior(sql_database):
    _engine, session_factory = sql_database
    tasks = [
        Task(1, "План задач %_", 2, tags=["one"]),
        Task(2, "План   задач", 3, tags=["spaces"]),
        Task(3, "ПЛАН задач %_", 4, is_done=True, tags=["duplicate"]),
        Task(4, "Plan API", 1),
        Task(5, "Quote ' inside", 2),
        Task(6, "План курса", 5),
    ]
    with session_factory() as session:
        session.add_all(
            [
                TaskRow(
                    id=task.id,
                    title=task.title,
                    priority=task.priority,
                    is_done=task.is_done,
                    tags=task.tags.copy(),
                    title_normalized=task.title.lower(),
                )
                for task in tasks
            ]
        )
        session.commit()

    with session_factory() as session:
        sql_repository = SqlTaskRepository(session)
        for query in [" ПЛАН ", "%_", "_", "'", "план задач", "  "]:
            assert isinstance(sql_repository.search(query), list)
        assert [task.id for task in sql_repository.search("%_")] == [1, 3]
        assert [task.id for task in sql_repository.search("план задач")] == [1, 3]
        assert sql_repository.search("  ") == []
        assert all(
            isinstance(task, Task) for task in sql_repository.search("план")
        )


def test_sql_search_uses_database_and_empty_query_skips_select(sql_database):
    engine, session_factory = sql_database
    with session_factory() as session:
        session.add(
            TaskRow(
                id=1,
                title="Курс 20%_ готов",
                priority=3,
                tags=["internal"],
                title_normalized="курс 20%_ готов",
            )
        )
        session.commit()

    selects = []

    def record_select(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    event.listen(engine, "before_cursor_execute", record_select)
    try:
        with session_factory() as session:
            repository = SqlTaskRepository(session)
            assert repository.search("  ") == []
            assert selects == []
            found = repository.search("%_")
            assert [task.id for task in found] == [1]
            assert found[0].tags == ["internal"]
    finally:
        event.remove(engine, "before_cursor_execute", record_select)

    assert len(selects) == 1
    assert "INSTR" in selects[0].upper()
    assert "ORDER BY" in selects[0].upper()


def test_sql_search_tracks_title_through_create_put_and_patch(
    sql_database, api_client, api_service
):
    _engine, session_factory = sql_database
    previous_factory = getattr(app.state, "session_factory", None)
    had_factory = hasattr(app.state, "session_factory")
    previous_overrides = app.dependency_overrides.copy()

    def get_sql_planner(db=Depends(get_db)):
        return build_service(
            repository=SqlTaskRepository(db),
            write_scope=db.begin,
        )

    app.state.session_factory = session_factory
    app.dependency_overrides[get_planner] = get_sql_planner
    try:
        created = api_client.post(
            "/tasks", json={"title": "ПЛАН старый", "priority": 2}
        )
        task_id = created.json()["id"]
        with session_factory() as session:
            repository = SqlTaskRepository(session)
            assert [task.id for task in repository.search("план")] == [task_id]

        replaced = api_client.put(
            f"/tasks/{task_id}",
            json={"title": "Курс Python", "priority": 4, "is_done": False},
        )
        with session_factory() as session:
            repository = SqlTaskRepository(session)
            assert repository.search("план") == []
            assert [task.id for task in repository.search("КУРС")] == [task_id]

        patched = api_client.patch(f"/tasks/{task_id}", json={"title": "Заметка"})
        with session_factory() as session:
            row = session.get(TaskRow, task_id)
            repository = SqlTaskRepository(session)
            assert repository.search("курс") == []
            assert [task.id for task in repository.search("ЗАМЕТКА")] == [task_id]
            assert row.title_normalized == "заметка"
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        if had_factory:
            app.state.session_factory = previous_factory
        else:
            del app.state.session_factory

    assert created.status_code == 201
    assert replaced.status_code == patched.status_code == 200
    sql_task = api_service.add_task("SQL default поиск", 1)
    assert [task.id for task in api_service.search_tasks("ПОИСК")] == [
        sql_task.id
    ]


def test_cli_sql_workflow_uses_one_closed_session_per_command(
    sql_database,
):
    engine, _session_factory = sql_database
    created_sessions = []

    class TrackedSession(Session):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.was_closed = False
            created_sessions.append(self)

        def close(self):
            self.was_closed = True
            super().close()

    tracked_factory = sessionmaker(bind=engine, class_=TrackedSession)
    entered = []
    exited = []

    @contextmanager
    def tracked_context():
        entered.append(len(entered) + 1)
        try:
            with sql_service_context(tracked_factory) as planner:
                yield planner
        finally:
            exited.append(len(exited) + 1)

    commands = iter(
        (
            "add", "CLI SQL task", "3",
            "list",
            "find", "1",
            "done", "1",
            "stats",
            "search", "SQL",
            "delete", "1",
            "unknown",
            "exit",
        )
    )
    output = []
    result = run(
        tracked_context,
        read=lambda _prompt: next(commands),
        write=output.append,
    )

    assert result is None
    assert entered == exited == list(range(1, 8))
    assert len(created_sessions) == 7
    assert all(session.was_closed for session in created_sessions)
    assert any("CLI SQL task" in line for line in output)
    assert any("Задача 1 выполнена" in line for line in output)
    assert any("Всего: 1" in line for line in output)
    assert any("неизвест" in line.casefold() for line in output)
    with _session_factory() as session:
        assert session.get(TaskRow, 1) is None
        assert session.scalars(select(TaskRow)).all() == []

def test_readiness_rehearsal_imports_copy_and_shares_sql_between_api_and_cli(
    sql_database, tmp_path, api_client, api_service
):
    engine, _session_factory = sql_database
    source_path = Path(__file__).resolve().parents[1] / "data" / "tasks.json"
    source_before = source_path.read_bytes()
    copied_snapshot = tmp_path / "snapshot-copy.json"
    shutil.copyfile(source_path, copied_snapshot)
    snapshot_before = copied_snapshot.read_bytes()
    source_records = json.loads(snapshot_before.decode("utf-8"))
    expected_rows = {
        record["id"]: (
            record["title"],
            record["priority"],
            record["is_done"],
            record.get("tags", []),
            record["title"].lower(),
        )
        for record in source_records
    }

    database_url = engine.url.render_as_string(hide_password=False)
    assert import_snapshot(copied_snapshot, database_url) == len(source_records)
    with _session_factory() as session:
        imported_rows = session.scalars(
            select(TaskRow).order_by(TaskRow.id)
        ).all()
        actual_rows = {
            row.id: (
                row.title,
                row.priority,
                row.is_done,
                row.tags,
                row.title_normalized,
            )
            for row in imported_rows
        }
    assert actual_rows == expected_rows

    created_sessions = []

    class TrackedSession(Session):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.was_closed = False
            created_sessions.append(self)

        def close(self):
            self.was_closed = True
            super().close()

    tracked_factory = sessionmaker(bind=engine, class_=TrackedSession)
    previous_factory = getattr(app.state, "session_factory", None)
    had_factory = hasattr(app.state, "session_factory")
    previous_overrides = app.dependency_overrides.copy()

    def get_sql_planner(db=Depends(get_db)):
        return build_service(
            repository=SqlTaskRepository(db),
            write_scope=db.begin,
        )

    app.state.session_factory = tracked_factory
    app.dependency_overrides[get_planner] = get_sql_planner
    output = []
    target = next(record for record in source_records if not record["is_done"])
    try:
        created = api_client.post(
            "/tasks", json={"title": "Приёмка блок 15", "priority": 3}
        )
        task_id = created.json()["id"]
        commands = iter(("find", str(task_id), "done", str(task_id), "stats", "exit"))
        run(
            lambda: sql_service_context(tracked_factory),
            read=lambda _prompt: next(commands),
            write=output.append,
        )
        fetched = api_client.get(f"/tasks/{task_id}")
        statistics = api_client.get("/stats")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        if had_factory:
            app.state.session_factory = previous_factory
        else:
            del app.state.session_factory

    assert created.status_code == 201
    assert created.json() == {
        "id": task_id,
        "title": "Приёмка блок 15",
        "priority": 3,
        "is_done": False,
    }
    assert fetched.status_code == 200
    assert fetched.json() == {
        "id": task_id,
        "title": "Приёмка блок 15",
        "priority": 3,
        "is_done": True,
    }
    assert statistics.json() == {
        "total": len(source_records) + 1,
        "open": sum(not item["is_done"] for item in source_records),
        "done": sum(item["is_done"] for item in source_records) + 1,
    }
    assert any(f"[{task_id}] Приёмка блок 15" in line for line in output)
    assert any(f"Задача {task_id} выполнена" in line for line in output)
    assert all(session.was_closed for session in created_sessions)
    assert len(created_sessions) == 6

    with _session_factory() as session:
        completed_row = session.get(TaskRow, task_id)
        unchanged_row = session.get(TaskRow, target["id"])
        assert completed_row.is_done is True
        assert completed_row.title_normalized == "приёмка блок 15"
        assert unchanged_row is not None
        assert (
            unchanged_row.title,
            unchanged_row.priority,
            unchanged_row.is_done,
            unchanged_row.tags,
            unchanged_row.title_normalized,
        ) == expected_rows[target["id"]]
        assert session.get(TaskRow, task_id - 1) is not None

    assert source_path.read_bytes() == source_before
    assert copied_snapshot.read_bytes() == snapshot_before
    assert len(api_service.snapshot()) == len(source_records) + 1


def test_unavailable_database_in_new_process_never_falls_back_to_json(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "missing-parent" / "unavailable.sqlite3"
    database_url = URL.create(
        "sqlite", database=database_path.as_posix()
    ).render_as_string(hide_password=False)
    legacy_snapshot = tmp_path / "tasks.json"
    legacy_content = b'[{"id": 1, "title": "stale", "priority": 1, "is_done": false}]'
    legacy_snapshot.write_bytes(legacy_content)
    code = r'''
import os
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from app.api import app
from app.DBase.engine import make_engine

closed = []
class TrackingSession(Session):
    def close(self):
        closed.append(True)
        super().close()

engine = make_engine(os.environ["DATABASE_URL"])
app.state.session_factory = sessionmaker(bind=engine, class_=TrackingSession)
with TestClient(app, raise_server_exceptions=False) as client:
    response = client.get("/tasks")
assert response.status_code == 500, response.status_code
assert closed == [True], closed
assert open(os.environ["LEGACY_SNAPSHOT"], "rb").read() == os.environ["LEGACY_CONTENT"].encode()
print("SQL failure propagated; session closed; legacy snapshot unchanged")
engine.dispose()
'''
    environment = os.environ.copy()
    environment.update(
        DATABASE_URL=database_url,
        JSON_PATH=str(legacy_snapshot),
        LEGACY_SNAPSHOT=str(legacy_snapshot),
        LEGACY_CONTENT=legacy_content.decode("ascii"),
        PYTHONPATH=str(project_root),
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        "SQL failure propagated; session closed; legacy snapshot unchanged"
    )
    assert legacy_snapshot.read_bytes() == legacy_content
    assert not database_path.parent.exists()
