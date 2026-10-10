from sqlalchemy import URL, select

from app.DBase.engine import make_engine
from app.DBase.init_db import initialize_database
from app.DBase.models import TaskRow, task_from_row
from app.DBase.session import make_session_factory
from app.core.config import Settings
from app.models import Task


def _session_factory_for(database_path):
    database_url = URL.create(
        "sqlite", database=database_path.as_posix()
    ).render_as_string(hide_password=False)
    settings = Settings(
        json_path=database_path.parent / "tasks.json",
        app_name="Test",
        database_url=database_url,
    )
    initialize_database(settings)
    engine = make_engine(database_url)
    return engine, make_session_factory(engine)


def test_select_and_mapping_return_independent_tasks_after_session_closes(tmp_path):
    engine, session_factory = _session_factory_for(tmp_path / "mapping.sqlite3")

    try:
        with session_factory() as session:
            session.add_all(
                [
                    TaskRow(
                        title="Первая задача",
                        priority=4,
                        tags=["python"],
                        title_normalized="первая задача",
                    ),
                    TaskRow(
                        title="Вторая задача",
                        priority=2,
                        is_done=True,
                        tags=["review"],
                        title_normalized="вторая задача",
                    ),
                ]
            )
            session.commit()

            statement = select(TaskRow).order_by(TaskRow.id)
            rows = session.scalars(statement).all()
            tasks = [task_from_row(row) for row in rows]

            existing_row = session.get(TaskRow, tasks[0].id)
            missing_row = session.get(TaskRow, 9999)
            existing_task = (
                task_from_row(existing_row) if existing_row is not None else None
            )
            missing_task = (
                task_from_row(missing_row) if missing_row is not None else None
            )

        assert [task.id for task in tasks] == [row.id for row in rows]
        assert all(isinstance(task, Task) for task in tasks)
        assert tasks[0].to_dict() == {
            "id": rows[0].id,
            "title": "Первая задача",
            "priority": 4,
            "is_done": False,
            "tags": ["python"],
        }
        assert tasks[1].to_dict() == {
            "id": rows[1].id,
            "title": "Вторая задача",
            "priority": 2,
            "is_done": True,
            "tags": ["review"],
        }
        assert existing_task == tasks[0]
        assert missing_task is None

        tasks[0].tags.append("local-only")
        assert tasks[1].tags == ["review"]
        assert rows[0].tags == ["python"]

        with session_factory() as verification_session:
            saved_rows = verification_session.scalars(
                select(TaskRow).order_by(TaskRow.id)
            ).all()
            assert [row.tags for row in saved_rows] == [["python"], ["review"]]
    finally:
        engine.dispose()


def test_empty_select_and_unknown_id_have_different_results(tmp_path):
    engine, session_factory = _session_factory_for(tmp_path / "empty.sqlite3")
    try:
        with session_factory() as session:
            rows = session.scalars(select(TaskRow).order_by(TaskRow.id)).all()
            missing_row = session.get(TaskRow, 9999)

        assert rows == []
        assert missing_row is None
    finally:
        engine.dispose()
