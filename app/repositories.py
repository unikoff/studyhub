from __future__ import annotations

from app.models import Task


class JsonTaskRepository:
    """Read Planner tasks through the existing JSON storage."""

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
