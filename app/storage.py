import json
from pathlib import Path

from app.errors import StorageError
from app.models import Task


def encode_tasks(tasks):
    return json.dumps(tasks, ensure_ascii=False, indent=2)


def decode_tasks(text):
    return json.loads(text)


def validate_loaded_tasks(tasks):
    if not isinstance(tasks, list):
        raise ValueError("Корень снимка должен быть списком")

    seen_ids = set()
    for index, task in enumerate(tasks):
        if not isinstance(task, Task):
            raise ValueError(f"tasks[{index}]: ожидается Task")

        try:
            if not isinstance(task.tags, list):
                raise ValueError("tags должны быть списком")
            checked_task = Task.from_dict(task.to_dict())
            if checked_task != task:
                raise ValueError("значения Task не нормализованы")
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError(f"tasks[{index}]: неверная задача") from error

        if task.id in seen_ids:
            raise ValueError(f"tasks[{index}].id: повторяется {task.id}")
        seen_ids.add(task.id)

    return tasks


def load_tasks(path: Path):
    try:
        with path.open("r", encoding="utf-8") as file:
            text = file.read()
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError) as error:
        raise StorageError("Не удалось прочитать файл задач") from error

    try:
        records = decode_tasks(text)
    except json.JSONDecodeError as error:
        raise StorageError("Файл задач содержит неверный JSON") from error

    try:
        if not isinstance(records, list):
            raise ValueError("Корень снимка должен быть списком")

        tasks = []
        for index, record in enumerate(records):
            try:
                task = Task.from_dict(record)
                if record.get("title") != task.title:
                    raise ValueError("название в снимке не нормализовано")
                tasks.append(task)
            except (AttributeError, TypeError, ValueError) as error:
                raise ValueError(f"tasks[{index}]: неверная запись") from error

        validate_loaded_tasks(tasks)
    except ValueError as error:
        raise StorageError("Файл задач имеет неверную форму") from error
    return tasks


def save_tasks(path: Path, tasks):
    try:
        validate_loaded_tasks(tasks)
        records = [task.to_dict() for task in tasks]
        text = encode_tasks(records)
    except (AttributeError, TypeError, ValueError) as error:
        raise StorageError("Нельзя сохранить неверный снимок") from error

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            file.write(text)
    except OSError as error:
        raise StorageError("Не удалось записать файл задач") from error
