from app.errors import TaskNotFoundError
from app.models import Task
from app.validators import validate_task_id


class PlannerService:
    def __init__(self, storage):
        self.storage = storage

    def _find_task(self, tasks, task_id):
        if type(task_id) is not int:
            raise ValueError("Номер задачи должен быть целым числом")
        task_id = validate_task_id(task_id)
        for task in tasks:
            if task.id == task_id:
                return task
        raise TaskNotFoundError(f"Задача с номером {task_id} не найдена")

    def list_tasks(self):
        return self.storage.load()

    def select_tasks(
        self,
        is_done: bool | None = None,
        sort_desc: bool = False,
        limit: int | None = None,
    ) -> list[Task]:
        tasks = self.list_tasks()

        if is_done is not None:
            tasks = [task for task in tasks if task.is_done == is_done]

        tasks = sorted(
            tasks,
            key=lambda task: task.id,
            reverse=sort_desc,
        )

        if limit is not None:
            tasks = tasks[:limit]

        return tasks

    def get_task(self, task_id):
        tasks = self.storage.load()
        return self._find_task(tasks, task_id)

    def search_tasks(self, query):
        query = query.strip().lower()
        if not query:
            return []
        return [task for task in self.storage.load() if query in task.title.lower()]

    def get_statistics(self):
        tasks = self.storage.load()
        done = sum(task.is_done for task in tasks)
        total = len(tasks)
        return {"all": total, "open": total - done, "done": done}

    def add_task(self, title, priority, tags=None):
        tasks = self.storage.load()
        task = Task(
            id=max((item.id for item in tasks), default=0) + 1,
            title=title,
            priority=priority,
            is_done=False,
            tags=list(tags) if tags is not None else [],
        )
        tasks.append(task)
        self.storage.save(tasks)
        return task

    def replace_task(self, task_id, *, title, priority, is_done):
        tasks = self.storage.load()
        current = self._find_task(tasks, task_id)
        index = tasks.index(current)
        updated = Task(
            id=current.id,
            title=title,
            priority=priority,
            is_done=is_done,
            tags=current.tags.copy(),
        )
        tasks[index] = updated
        self.storage.save(tasks)
        return updated

    def patch_task(
        self, task_id, *, title=None, priority=None, is_done=None
    ):
        tasks = self.storage.load()
        current = self._find_task(tasks, task_id)
        if title is None and priority is None and is_done is None:
            return current

        index = tasks.index(current)
        updated = Task(
            id=current.id,
            title=current.title if title is None else title,
            priority=current.priority if priority is None else priority,
            is_done=current.is_done if is_done is None else is_done,
            tags=current.tags.copy(),
        )
        tasks[index] = updated
        self.storage.save(tasks)
        return updated

    def mark_done(self, task_id):
        tasks = self.storage.load()
        task = self._find_task(tasks, task_id)
        if task.is_done:
            return task
        task.mark_done()
        self.storage.save(tasks)
        return task

    def delete_task(self, task_id):
        tasks = self.storage.load()
        task = self._find_task(tasks, task_id)
        tasks.remove(task)
        self.storage.save(tasks)
        return None