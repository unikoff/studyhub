import json
from pathlib import Path

from app.errors import StorageError
from app.models import Task


def validate_loaded_tasks(records):
    if not isinstance(records, list):
        raise ValueError("Корень снимка должен быть списком")

    seen_ids = set()
    for index, record in enumerate(records):
        task = Task.from_dict(record)
        if task.title != record["title"]:
            raise ValueError(f"tasks[{index}].title: название не нормализовано")
        if "tags" in record and task.tags != record["tags"]:
            raise ValueError(f"tasks[{index}].tags: метки не нормализованы")
        if task.id in seen_ids:
            raise ValueError(f"tasks[{index}].id: повторяется {task.id}")
        seen_ids.add(task.id)

    return records


class JsonStorage:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[Task]:
        try:
            with self.path.open("r", encoding="utf-8") as file:
                text = file.read()
        except FileNotFoundError:
            return []
        except (OSError, UnicodeDecodeError) as error:
            raise StorageError("Не удалось прочитать файл задач") from error

        try:
            records = json.loads(text)
            validate_loaded_tasks(records)
            return [Task.from_dict(record) for record in records]
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise StorageError("Файл задач содержит неверный JSON или форму") from error

    def save(self, tasks: list[Task]) -> None:
        try:
            if not isinstance(tasks, list):
                raise ValueError("Корень снимка должен быть списком")
            records = []
            for index, task in enumerate(tasks):
                if not isinstance(task, Task):
                    raise ValueError(f"tasks[{index}]: ожидается Task")
                if not isinstance(task.tags, list):
                    raise ValueError(f"tasks[{index}].tags: ожидается список")
                records.append(task.to_dict())
            validate_loaded_tasks(records)
            text = json.dumps(records, ensure_ascii=False, indent=2)
        except (AttributeError, TypeError, ValueError) as error:
            raise StorageError("Нельзя сохранить неверный снимок") from error

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as file:
                file.write(text)
        except OSError as error:
            raise StorageError("Не удалось записать файл задач") from error
