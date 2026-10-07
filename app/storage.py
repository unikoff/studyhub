import json
from pathlib import Path

from app.errors import StorageError
from app.validators import (
    validate_priority,
    validate_task_id,
    validate_task_record,
    validate_title,
)


def encode_tasks(tasks):
    return json.dumps(tasks, ensure_ascii=False, indent=2)


def decode_tasks(text):
    return json.loads(text)


def validate_loaded_tasks(tasks):
    if not isinstance(tasks, list):
        raise ValueError("Корень снимка должен быть списком")

    seen_ids = set()
    for index, task in enumerate(tasks):
        validate_task_record(task, f"tasks[{index}]")

        task_id = task["id"]
        title = task["title"]
        priority = task["priority"]
        is_done = task["is_done"]

        if type(task_id) is not int:
            raise ValueError(f"tasks[{index}].id: ожидается целое число")
        if type(priority) is not int:
            raise ValueError(f"tasks[{index}].priority: ожидается целое число")
        if type(title) is not str:
            raise ValueError(f"tasks[{index}].title: ожидается строка")
        if type(is_done) is not bool:
            raise ValueError(f"tasks[{index}].is_done: ожидается bool")

        try:
            validate_task_id(task_id)
        except ValueError as error:
            raise ValueError(f"tasks[{index}].id: {error}") from error

        try:
            validate_priority(priority)
        except ValueError as error:
            raise ValueError(f"tasks[{index}].priority: {error}") from error

        try:
            normalized_title = validate_title(title)
        except ValueError as error:
            raise ValueError(f"tasks[{index}].title: {error}") from error
        if normalized_title != title:
            raise ValueError(f"tasks[{index}].title: название не нормализовано")

        if task_id in seen_ids:
            raise ValueError(f"tasks[{index}].id: повторяется {task_id}")
        seen_ids.add(task_id)

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
        tasks = decode_tasks(text)
    except json.JSONDecodeError as error:
        raise StorageError("Файл задач содержит неверный JSON") from error

    try:
        validate_loaded_tasks(tasks)
    except ValueError as error:
        raise StorageError("Файл задач имеет неверную форму") from error
    return tasks


def save_tasks(path: Path, tasks):
    try:
        validate_loaded_tasks(tasks)
    except ValueError as error:
        raise StorageError("Нельзя сохранить неверный снимок") from error
    text = encode_tasks(tasks)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            file.write(text)
    except OSError as error:
        raise StorageError("Не удалось записать файл задач") from error
