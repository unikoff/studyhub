from sqlalchemy import Boolean, CheckConstraint, Integer, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.models import Task


class Base(DeclarativeBase):
    pass


class TaskRow(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("id > 0", name="ck_tasks_id_positive"),
        CheckConstraint(
            "priority BETWEEN 1 AND 5", name="ck_tasks_priority_range"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    is_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    title_normalized: Mapped[str] = mapped_column(String, nullable=False)


def task_from_row(row: TaskRow) -> Task:
    return Task(
        id=row.id,
        title=row.title,
        priority=row.priority,
        is_done=row.is_done,
        tags=list(row.tags),
    )
