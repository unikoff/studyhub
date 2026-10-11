from contextlib import contextmanager

import pytest
from sqlalchemy import select
import subprocess
import sys

from app.cli import execute_command, run
from app.main import sql_service_context
from app.DBase.models import TaskRow


def seed_task(session_factory, *, done=False):
    with session_factory() as session:
        row = TaskRow(
            title="Python", priority=3, is_done=done, tags=[],
            title_normalized="python",
        )
        session.add(row)
        session.commit()
        return row.id


def test_mutating_commands_change_sql_state(sql_database):
    _engine, session_factory = sql_database
    task_id = seed_task(session_factory)
    commands = iter(("done", str(task_id), "exit"))
    output = []

    run(
        lambda: sql_service_context(session_factory),
        read=lambda _prompt: next(commands),
        write=output.append,
    )

    with session_factory() as session:
        row = session.get(TaskRow, task_id)
        assert row.is_done is True
    assert any(f"Задача {task_id} выполнена" in line for line in output)


def test_add_command_persists_normalized_task(sql_database):
    _engine, session_factory = sql_database
    commands = iter(("add", "  Новая задача  ", "2", "exit"))
    output = []

    run(
        lambda: sql_service_context(session_factory),
        read=lambda _prompt: next(commands),
        write=output.append,
    )

    with session_factory() as session:
        rows = session.scalars(select(TaskRow)).all()
        assert [(row.title, row.priority, row.is_done) for row in rows] == [
            ("Новая задача", 2, False)
        ]
    assert any("Новая задача" in line for line in output)


def test_read_commands_show_sql_result(sql_database):
    _engine, session_factory = sql_database
    seed_task(session_factory, done=True)
    commands = iter(("list", "stats", "exit"))
    output = []

    run(
        lambda: sql_service_context(session_factory),
        read=lambda _prompt: next(commands),
        write=output.append,
    )

    rendered = "\n".join(output)
    assert "Python" in rendered
    assert "Всего: 1" in rendered
    assert "Выполнено: 1" in rendered


def test_cli_unknown_and_exit_do_not_open_service_context():
    opened = []

    @contextmanager
    def service_scope():
        opened.append(True)
        yield object()

    messages = []
    assert execute_command(service_scope, "unknown", write=messages.append)
    assert not execute_command(service_scope, "exit", write=messages.append)
    assert opened == []
    assert any("неизвест" in message.casefold() for message in messages)


def test_cli_context_closes_when_service_fails():
    closed = []

    @contextmanager
    def service_scope():
        try:
            class BrokenService:
                def list_tasks(self):
                    raise RuntimeError("service failed")

            yield BrokenService()
        finally:
            closed.append(True)

    with pytest.raises(RuntimeError, match="service failed"):
        execute_command(service_scope, "list", write=lambda _message: None)
    assert closed == [True]


def test_import_main_does_not_start_cli():
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        capture_output=True, text=True, timeout=10, check=True,
    )
    assert result.stdout == ""
    assert result.stderr == ""
