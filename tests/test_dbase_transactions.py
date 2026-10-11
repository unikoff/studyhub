import pytest
from sqlalchemy import URL, func, select
from sqlalchemy.exc import IntegrityError, PendingRollbackError

from app.DBase.engine import make_engine
from app.DBase.init_db import initialize_database
from app.DBase.models import TaskRow
from app.DBase.session import make_session_factory
from app.core.config import Settings


@pytest.fixture
def isolated_database(tmp_path):
    database_path = tmp_path / "transactions.sqlite3"
    database_url = URL.create(
        "sqlite", database=database_path.as_posix()
    ).render_as_string(hide_password=False)
    settings = Settings(
        app_name="Test",
        database_url=database_url,
    )
    initialize_database(settings)
    engine = make_engine(settings.database_url)
    try:
        yield engine, make_session_factory(engine)
    finally:
        engine.dispose()


def _task(title, priority=2):
    return TaskRow(
        title=title,
        priority=priority,
        title_normalized=title.lower(),
    )


def test_rollback_removes_flushed_but_uncommitted_row(isolated_database):
    _, session_factory = isolated_database

    with session_factory() as session:
        row = _task("Отменённая задача")
        session.add(row)
        session.flush()
        task_id = row.id
        assert type(task_id) is int

        session.rollback()

    with session_factory() as verification_session:
        assert verification_session.get(TaskRow, task_id) is None


def test_failed_second_insert_rolls_back_both_rows(isolated_database):
    _, session_factory = isolated_database
    first_row = _task("Первая связанная задача")
    invalid_row = _task("Задача с неверным приоритетом", priority=6)

    with pytest.raises(IntegrityError):
        with session_factory() as session:
            with session.begin():
                session.add(first_row)
                session.flush()
                assert type(first_row.id) is int

                session.add(invalid_row)
                session.flush()

    with session_factory() as verification_session:
        assert verification_session.scalar(
            select(func.count()).select_from(TaskRow)
        ) == 0


def test_same_session_requires_rollback_before_next_query(isolated_database):
    _, session_factory = isolated_database

    with session_factory() as session:
        invalid_row = _task("Ошибка при flush", priority=6)
        session.add(invalid_row)

        with pytest.raises(IntegrityError):
            session.flush()

        assert session.is_active is False
        with pytest.raises(PendingRollbackError):
            session.scalar(select(TaskRow.id))

        session.rollback()
        assert session.is_active is True

        valid_row = _task("Новая операция после rollback")
        session.add(valid_row)
        session.flush()
        valid_id = valid_row.id
        session.commit()

    with session_factory() as verification_session:
        assert verification_session.get(TaskRow, valid_id) is not None
        assert verification_session.scalar(
            select(func.count()).select_from(TaskRow)
        ) == 1


def test_exception_rolls_back_and_closes_session_connection(isolated_database):
    engine, session_factory = isolated_database
    row = _task("Отменено исключением")

    with pytest.raises(RuntimeError, match="stop operation"):
        with session_factory() as session:
            with session.begin():
                session.add(row)
                session.flush()
                assert engine.pool.checkedout() == 1
                raise RuntimeError("stop operation")

    assert engine.pool.checkedout() == 0
    with session_factory() as verification_session:
        assert verification_session.scalar(
            select(func.count()).select_from(TaskRow)
        ) == 0
