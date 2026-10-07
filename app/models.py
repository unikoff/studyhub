from app.validators import (
    validate_priority,
    validate_task_id,
    validate_task_record,
    validate_title,
)


def create_task(task_id, title, priority=2):
    task_id = validate_task_id(task_id)
    title = validate_title(title)
    priority = validate_priority(priority)
    return {
        "id": task_id,
        "title": title,
        "priority": priority,
        "is_done": False,
    }


class Task:
    def __init__(
        self,
        id: int,
        title: str,
        priority: int = 2,
        is_done: bool = False,
    ) -> None:
        if type(id) is not int:
            raise ValueError("id должен быть целым числом")
        if type(priority) is not int:
            raise ValueError("priority должен быть целым числом")
        if type(is_done) is not bool:
            raise ValueError("is_done должен быть bool")

        checked_id = validate_task_id(id)
        checked_title = validate_title(title)
        checked_priority = validate_priority(priority)

        self.id = checked_id
        self.title = checked_title
        self.priority = checked_priority
        self.is_done = is_done

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
        }

    @classmethod
    def from_dict(cls, record):
        validate_task_record(record)
        return cls(
            id=record["id"],
            title=record["title"],
            priority=record["priority"],
            is_done=record["is_done"],
        )
