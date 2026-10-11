from sqlalchemy import select
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
