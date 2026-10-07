from dataclasses import dataclass, field

from app.validators import (
    validate_priority,
    validate_task_id,
    validate_task_record,
    validate_tags,
    validate_title,
)



@dataclass
class Task:
    id: int
    title: str
    priority: int = 2
    is_done: bool = False
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if type(self.id) is not int:
            raise ValueError("id должен быть целым числом")
        if type(self.priority) is not int:
            raise ValueError("priority должен быть целым числом")
        if type(self.is_done) is not bool:
            raise ValueError("is_done должен быть bool")

        self.id = validate_task_id(self.id)
        self.title = validate_title(self.title)
        self.priority = validate_priority(self.priority)
        self.tags = validate_tags(self.tags)

    def mark_done(self) -> None:
        self.is_done = True

    def rename(self, title: str) -> None:
        checked_title = validate_title(title)
        self.title = checked_title

    def set_priority(self, priority: int) -> None:
        checked_priority = validate_priority(priority)
        self.priority = checked_priority

    @property
    def status_label(self) -> str:
        if self.is_done:
            return "выполнена"
        return "не завершена"

    def __str__(self) -> str:
        return (
            f"[{self.id}] {self.title} | "
            f"приоритет: {self.priority} | {self.status_label}"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority,
            "is_done": self.is_done,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, record):
        if not isinstance(record, dict):
            raise ValueError("Запись задачи должна быть словарём")

        old_fields = {"id", "title", "priority", "is_done"}
        record_fields = set(record)
        if record_fields == old_fields:
            tags = []
        elif record_fields == old_fields | {"tags"}:
            tags = record["tags"]
        else:
            raise ValueError("Неверный набор полей задачи")

        legacy_record = {key: record[key] for key in old_fields}
        validate_task_record(legacy_record)
        return cls(
            id=record["id"],
            title=record["title"],
            priority=record["priority"],
            is_done=record["is_done"],
            tags=tags,
        )
