from __future__ import annotations

from app.models import Task


class JsonTaskRepository:
    """Read and change Planner tasks through the existing JSON storage."""

    def __init__(self, storage):
        self.storage = storage

    def list(self) -> list[Task]:
        return self.storage.load()

    def get(self, task_id: int) -> Task | None:
        return next(
            (task for task in self.storage.load() if task.id == task_id),
            None,
        )

    def select(
        self,
        is_done: bool | None = None,
        sort_desc: bool = False,
        limit: int | None = None,
    ) -> list[Task]:
        tasks = self.storage.load()

        if is_done is not None:
            tasks = [task for task in tasks if task.is_done == is_done]

        tasks = sorted(tasks, key=lambda task: task.id, reverse=sort_desc)

        if limit is not None:
            tasks = tasks[:limit]

        return tasks

    def search(self, query: str) -> list[Task]:
        query = query.strip().lower()
        if not query:
            return []
        return [
            task for task in self.storage.load() if query in task.title.lower()
        ]

    def statistics(self) -> dict[str, int]:
        tasks = self.storage.load()
        done = sum(task.is_done for task in tasks)
        total = len(tasks)
        return {"all": total, "open": total - done, "done": done}

    def create(self, title: str, priority: int, tags=None) -> Task:
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

    def _store_updated_task(self, task_id: int, task: Task) -> Task | None:
        tasks = self.storage.load()
        for index, current in enumerate(tasks):
            if current.id == task_id:
                tasks[index] = task
                self.storage.save(tasks)
                return task
        return None

    def replace(self, task_id: int, task: Task) -> Task | None:
        return self._store_updated_task(task_id, task)

    def update(self, task_id: int, task: Task) -> Task | None:
        return self._store_updated_task(task_id, task)

    def delete(self, task_id: int) -> bool:
        tasks = self.storage.load()
        for index, task in enumerate(tasks):
            if task.id == task_id:
                del tasks[index]
                self.storage.save(tasks)
                return True
        return False
