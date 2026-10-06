import json
from pathlib import Path

from app.validators import validate_priority, validate_task_id, validate_title


TASK_FIELDS = {"id", "title", "priority", "is_done"}


def encode_tasks(tasks):
    return json.dumps(tasks, ensure_ascii=False, indent=2)


def decode_tasks(text):
    return json.loads(text)


def validate_loaded_tasks(tasks):
    if not isinstance(tasks, list):
        raise ValueError("Корень снимка должен быть списком")

    seen_ids = set()
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError(f"tasks[{index}]: ожидается словарь")
        if set(task) != TASK_FIELDS:
            raise ValueError(f"tasks[{index}]: неверный набор полей")

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
    return validate_loaded_tasks(decode_tasks(text))


def save_tasks(path: Path, tasks):
    validate_loaded_tasks(tasks)
    text = encode_tasks(tasks)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        file.write(text)
