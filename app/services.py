from contextlib import nullcontext

from app.errors import TaskNotFoundError
from app.models import Task
from app.repositories import JsonTaskRepository
from app.validators import (
    validate_priority,
    validate_tags,
    validate_task_id,
    validate_title,
)


class PlannerService:
    def __init__(self, storage=None, repository=None, write_scope=None):
        if storage is not None and repository is not None:
            raise ValueError("Pass either storage or repository, not both")
        if storage is None and repository is None:
            raise ValueError("Pass storage or repository")

        self.storage = storage
        self.repository = (
            JsonTaskRepository(storage) if repository is None else repository
        )
        self.write_scope = write_scope if write_scope is not None else nullcontext

    def _validate_task_id(self, task_id):
        if type(task_id) is not int:
            raise ValueError("Номер задачи должен быть целым числом")
        return validate_task_id(task_id)

    @staticmethod
    def _raise_task_not_found(task_id):
        raise TaskNotFoundError(f"Задача с номером {task_id} не найдена")

    def list_tasks(self):
        return self.repository.list()

    def select_tasks(
        self,
        is_done: bool | None = None,
        sort_desc: bool = False,
        limit: int | None = None,
    ) -> list[Task]:
        return self.repository.select(
            is_done=is_done,
            sort_desc=sort_desc,
            limit=limit,
        )

    def get_task(self, task_id):
        task_id = self._validate_task_id(task_id)
        task = self.repository.get(task_id)
        if task is None:
            self._raise_task_not_found(task_id)
        return task

    def search_tasks(self, query):
        return self.repository.search(query)

    def get_statistics(self):
        return self.repository.statistics()

    def add_task(self, title, priority, tags=None):
        title = validate_title(title)
        priority = validate_priority(priority)
        tags = validate_tags([] if tags is None else tags)

        with self.write_scope():
            task = self.repository.create(title, priority, tags)
        return task

    def replace_task(self, task_id, *, title, priority, is_done):
        current = self.get_task(task_id)
        updated = Task(
            id=current.id,
            title=title,
            priority=priority,
            is_done=is_done,
            tags=current.tags.copy(),
        )
        saved = self.repository.replace(current.id, updated)
        if saved is None:
            self._raise_task_not_found(current.id)
        return saved

    def patch_task(
        self, task_id, *, title=None, priority=None, is_done=None
    ):
        current = self.get_task(task_id)
        if title is None and priority is None and is_done is None:
            return current

        updated = Task(
            id=current.id,
            title=current.title if title is None else title,
            priority=current.priority if priority is None else priority,
            is_done=current.is_done if is_done is None else is_done,
            tags=current.tags.copy(),
        )
        saved = self.repository.update(current.id, updated)
        if saved is None:
            self._raise_task_not_found(current.id)
        return saved

    def mark_done(self, task_id):
        task = self.get_task(task_id)
        if task.is_done:
            return task
        updated = Task(
            id=task.id,
            title=task.title,
            priority=task.priority,
            is_done=True,
            tags=task.tags.copy(),
        )
        saved = self.repository.update(updated.id, updated)
        if saved is None:
            self._raise_task_not_found(updated.id)
        return saved

    def delete_task(self, task_id):
        task = self.get_task(task_id)
        if not self.repository.delete(task.id):
            self._raise_task_not_found(task.id)
        return None
