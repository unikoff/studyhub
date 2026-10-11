import pytest
from fastapi import Depends
from sqlalchemy import URL, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.api import app
from app.core.dependencies import get_db, get_planner
from app.DBase.engine import make_engine
from app.DBase.init_db import initialize_database
from app.DBase.models import TaskRow
from app.DBase.session import make_session_factory
from app.core.config import Settings
from app.main import build_service, sql_service_context
from app.models import Task
from app.repositories import JsonTaskRepository
from app.DBase.repositories import SqlTaskRepository
from app.storage import JsonStorage, MemoryStorage


@pytest.fixture
def sql_database(tmp_path):
    database_path = tmp_path / "planner.sqlite3"
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
    json_repository = JsonTaskRepository(MemoryStorage(expected))
    assert tasks == json_repository.list()
    assert existing == json_repository.get(8)

    tasks[1].tags.append("local-only")
    assert tasks[0].tags == ["review"]

    with session_factory() as verification_session:
        rows = verification_session.scalars(
            select(TaskRow).order_by(TaskRow.id)
        ).all()
        assert [row.tags for row in rows] == [["review"], ["sql", "reading"]]


def test_sql_get_provider_uses_a_request_session_and_restores_json(
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
    json_task = api_service.add_task("JSON task", 2)

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
    json_response = api_client.get(f"/tasks/{json_task.id}")
    assert json_response.status_code == 200
    assert json_response.json()["title"] == "JSON task"


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


def test_sql_post_uses_generated_id_and_restores_json_provider(
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
    assert not api_service.storage.path.exists()

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

    json_response = api_client.post(
        "/tasks", json={"title": "JSON task", "priority": 2}
    )
    assert json_response.status_code == 201
    assert json_response.json()["id"] == 1
    assert api_service.get_task(1).title == "JSON task"


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
