from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.DBase.models import TaskRow, task_from_row
from app.models import Task


class SqlTaskRepository:
    def __init__(self, session: Session):
        self.session = session

    def list(self) -> list[Task]:
        statement = select(TaskRow).order_by(TaskRow.id)
        rows = self.session.scalars(statement).all()
        return [task_from_row(row) for row in rows]

    def select(
        self,
        is_done: bool | None = None,
        sort_desc: bool = False,
        limit: int | None = None,
    ) -> list[Task]:
        statement = select(TaskRow)
        if is_done is not None:
            statement = statement.where(TaskRow.is_done == is_done)

        ordering = TaskRow.id.desc() if sort_desc else TaskRow.id.asc()
        statement = statement.order_by(ordering)
        if limit is not None:
            statement = statement.limit(limit)

        rows = self.session.scalars(statement).all()
        return [task_from_row(row) for row in rows]

    def search(self, query: str) -> list[Task]:
        query = query.strip().lower()
        if not query:
            return []

        statement = (
            select(TaskRow)
            .where(func.instr(TaskRow.title_normalized, query) > 0)
            .order_by(TaskRow.id)
        )
        rows = self.session.scalars(statement).all()
        return [task_from_row(row) for row in rows]

    def statistics(self) -> dict[str, int]:
        statement = select(
            func.count(TaskRow.id),
            func.count(case((TaskRow.is_done.is_(False), TaskRow.id))),
            func.count(case((TaskRow.is_done.is_(True), TaskRow.id))),
        )
        total, opened, done = self.session.execute(statement).one()
        return {"all": total, "open": opened, "done": done}

    def get(self, task_id: int) -> Task | None:
        row = self.session.get(TaskRow, task_id)
        if row is None:
            return None
        return task_from_row(row)

    def create(self, title: str, priority: int, tags=None) -> Task:
        row = TaskRow(
            title=title,
            priority=priority,
            is_done=False,
            tags=list(tags) if tags is not None else [],
            title_normalized=title.lower(),
        )
        self.session.add(row)
        self.session.flush()
        return task_from_row(row)

    def replace(self, task_id: int, task: Task) -> Task | None:
        row = self.session.get(TaskRow, task_id)
        if row is None:
            return None

        row.title = task.title
        row.priority = task.priority
        row.is_done = task.is_done
        row.tags = task.tags.copy()
        row.title_normalized = task.title.lower()
        self.session.flush()
        return task_from_row(row)

    def update(self, task_id: int, task: Task) -> Task | None:
        row = self.session.get(TaskRow, task_id)
        if row is None:
            return None

        row.title = task.title
        row.priority = task.priority
        row.is_done = task.is_done
        row.tags = task.tags.copy()
        row.title_normalized = task.title.lower()
        self.session.flush()
        return task_from_row(row)

    def delete(self, task_id: int) -> bool:
        row = self.session.get(TaskRow, task_id)
        if row is None:
            return False

        self.session.delete(row)
        return True
