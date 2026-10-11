from dataclasses import dataclass
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Task
from app.services import PlannerService
from app.DBase.repositories import SqlTaskRepository


def get_db(request: Request) -> Iterator[Session]:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise RuntimeError("SQL session factory is not configured")

    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def get_planner(db: Session = Depends(get_db)) -> PlannerService:
    return PlannerService(
        repository=SqlTaskRepository(db),
        write_scope=db.begin,
    )


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


PlannerDep = Annotated[PlannerService, Depends(get_planner)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@dataclass(frozen=True)
class SelectionParams:
    is_done: bool | None = None
    sort_desc: bool = False
    limit: int = 10


def get_selection(
    is_done: Annotated[bool | None, Query()] = None,
    sort_desc: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> SelectionParams:
    return SelectionParams(is_done, sort_desc, limit)


def get_selected_tasks(
    planner: PlannerDep,
    selection: Annotated[SelectionParams, Depends(get_selection)],
) -> list[Task]:
    return planner.select_tasks(
        is_done=selection.is_done,
        sort_desc=selection.sort_desc,
        limit=selection.limit,
    )
