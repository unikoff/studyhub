from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response, status

from app.errors import TaskNotFoundError
from .schemas import TaskCreate, TaskPatch, TaskRead, TaskUpdate


router = APIRouter(prefix="/tasks", tags=["tasks"])


def _call_with_task_not_found_as_404(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        ) from error


def _task_read_data(task):
    return {
        "id": task.id,
        "title": task.title,
        "priority": task.priority,
        "is_done": task.is_done,
    }


@router.get("", response_model=list[TaskRead])
def read_tasks(
    request: Request,
    is_done: bool | None = None,
    sort_desc: bool = False,
    limit: int = Query(default=10, ge=1, le=50),
):
    tasks = request.app.state.planner.select_tasks(
        is_done=is_done,
        sort_desc=sort_desc,
        limit=limit,
    )
    return [_task_read_data(task) for task in tasks]


@router.get("/{task_id}", response_model=TaskRead)
def read_task(
    request: Request, task_id: Annotated[int, Path(gt=0)]
):
    task = _call_with_task_not_found_as_404(
        request.app.state.planner.get_task, task_id
    )
    return _task_read_data(task)


@router.put("/{task_id}", response_model=TaskRead)
def update_task(
    request: Request,
    task_id: Annotated[int, Path(gt=0)],
    payload: TaskUpdate,
):
    task = _call_with_task_not_found_as_404(
        request.app.state.planner.replace_task,
        task_id,
        title=payload.title,
        priority=payload.priority,
        is_done=payload.is_done,
    )
    return _task_read_data(task)


@router.patch("/{task_id}", response_model=TaskRead)
def patch_task_endpoint(
    request: Request,
    task_id: Annotated[int, Path(gt=0)],
    payload: TaskPatch,
):
    changes = payload.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )
    task = _call_with_task_not_found_as_404(
        request.app.state.planner.patch_task, task_id, **changes
    )
    return _task_read_data(task)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_task_endpoint(
    request: Request, task_id: Annotated[int, Path(gt=0)]
):
    _call_with_task_not_found_as_404(
        request.app.state.planner.delete_task, task_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TaskRead)
def create_task(request: Request, payload: TaskCreate):
    try:
        task = request.app.state.planner.add_task(
            payload.title,
            priority=payload.priority,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return _task_read_data(task)
