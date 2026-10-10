import argparse
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.DBase.engine import make_engine
from app.DBase.models import TaskRow
from app.DBase.session import make_session_factory
from app.models import Task


class SnapshotImportError(ValueError):
    pass


def load_snapshot(source_path: Path) -> list[Task]:
    try:
        text = source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise SnapshotImportError(
            f"Не удалось прочитать источник {source_path}: {error}"
        ) from error

    try:
        records = json.loads(text)
    except json.JSONDecodeError as error:
        raise SnapshotImportError(
            f"Некорректный JSON, строка {error.lineno}, столбец {error.colno}"
        ) from error

    if not isinstance(records, list):
        raise SnapshotImportError("Корень снимка должен быть списком")

    tasks = []
    seen_ids = set()
    for index, record in enumerate(records):
        try:
            task = Task.from_dict(record)
            if task.title != record["title"]:
                raise ValueError("название не нормализовано")
            if "tags" in record and task.tags != record["tags"]:
                raise ValueError("метки не нормализованы")
            if task.id in seen_ids:
                raise ValueError(f"id {task.id} повторяется")
        except (KeyError, TypeError, ValueError) as error:
            raise SnapshotImportError(f"tasks[{index}]: {error}") from error

        seen_ids.add(task.id)
        tasks.append(task)

    return tasks


def _write_snapshot(
    tasks: list[Task], session_factory: sessionmaker[Session]
) -> None:
    rows = [
        TaskRow(
            id=task.id,
            title=task.title,
            priority=task.priority,
            is_done=task.is_done,
            tags=list(task.tags),
            title_normalized=task.title.lower(),
        )
        for task in tasks
    ]

    with session_factory() as session:
        try:
            existing_id = session.scalar(select(TaskRow.id).limit(1))
            if existing_id is not None:
                raise SnapshotImportError("Целевая таблица tasks не пуста")

            session.add_all(rows)
            session.commit()
        except Exception:
            session.rollback()
            raise


def _verify_snapshot(
    tasks: list[Task], session_factory: sessionmaker[Session]
) -> None:
    expected = {
        task.id: (
            task.title,
            task.priority,
            task.is_done,
            task.tags,
            task.title.lower(),
        )
        for task in tasks
    }

    with session_factory() as session:
        rows = session.scalars(select(TaskRow).order_by(TaskRow.id)).all()
        actual = {
            row.id: (
                row.title,
                row.priority,
                row.is_done,
                row.tags,
                row.title_normalized,
            )
            for row in rows
        }

    if actual != expected:
        raise SnapshotImportError(
            "Сохранённые задачи не совпадают с проверенным снимком"
        )


def import_snapshot(source_path: Path, database_url: str) -> int:
    tasks = load_snapshot(source_path)
    engine = make_engine(database_url)
    try:
        session_factory = make_session_factory(engine)
        _write_snapshot(tasks, session_factory)
        _verify_snapshot(tasks, session_factory)
    finally:
        engine.dispose()

    return len(tasks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Однократно перенести JSON-снимок в пустую SQLite-базу."
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args(argv)

    try:
        count = import_snapshot(args.source, args.database_url)
    except (SnapshotImportError, SQLAlchemyError) as error:
        parser.exit(1, f"Ошибка импорта: {error}\n")

    print(f"Импортировано задач: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
