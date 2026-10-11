import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import URL

from app.api import app
from app.core.config import Settings
from app.DBase.engine import make_engine
from app.DBase.init_db import initialize_database
from app.DBase.models import TaskRow
from app.DBase.repositories import SqlTaskRepository
from app.DBase.session import make_session_factory
from app.main import build_service
from app.models import Task


@pytest.fixture
def task():
    return Task(1, "Python", 3, tags=["study"])


@pytest.fixture
def sql_database(tmp_path):
    database_path = tmp_path / "planner.sqlite3"
    database_url = URL.create(
        "sqlite", database=database_path.as_posix()
    ).render_as_string(hide_password=False)
    settings = Settings(app_name="Test Planner", database_url=database_url)
    initialize_database(settings)
    engine = make_engine(database_url)
    try:
        yield engine, make_session_factory(engine)
    finally:
        engine.dispose()


class DatabasePlanner:
    def __init__(self, session_factory, database_path):
        self.session_factory = session_factory
        self.database_path = database_path

    def __getattr__(self, name):
        def call(*args, **kwargs):
            with self.session_factory() as db:
                service = build_service(SqlTaskRepository(db), db.begin)
                return getattr(service, name)(*args, **kwargs)
        return call

    def snapshot(self):
        with self.session_factory() as db:
            rows = db.scalars(select(TaskRow).order_by(TaskRow.id)).all()
            return [
                (row.id, row.title, row.priority, row.is_done, list(row.tags))
                for row in rows
            ]


@pytest.fixture
def api_service(sql_database):
    _engine, session_factory = sql_database
    database_path = session_factory.kw["bind"].url.database
    return DatabasePlanner(session_factory, database_path)


@pytest.fixture
def api_client(api_service, sql_database):
    _engine, session_factory = sql_database
    previous_factory = app.state.session_factory
    previous_overrides = app.dependency_overrides.copy()
    app.state.session_factory = session_factory
    try:
        with TestClient(app, follow_redirects=False) as test_client:
            yield test_client
    finally:
        app.state.session_factory = previous_factory
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
