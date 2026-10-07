from app.validators import validate_priority, validate_task_id, validate_title


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
