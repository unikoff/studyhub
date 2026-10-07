from typing import Annotated

from fastapi import (
    FastAPI,
    HTTPException,
    Path as PathParam,
    Query,
    Response,
    status,
)

from app.errors import TaskNotFoundError
from app.main import build_service
from app.schemas import TaskCreate, TaskPatch, TaskRead, TaskUpdate


app = FastAPI(title="StudyHub Planner")
app.state.planner = build_service()


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


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/tasks", response_model=list[TaskRead])
def read_tasks(
    is_done: bool | None = None,
    sort_desc: bool = False,
    limit: int = Query(default=10, ge=1, le=50),
):
    tasks = app.state.planner.select_tasks(
        is_done=is_done,
        sort_desc=sort_desc,
        limit=limit,
    )
    return [_task_read_data(task) for task in tasks]


@app.get("/stats")
def read_stats():
    statistics = app.state.planner.get_statistics()
    return {
        "total": statistics["all"],
        "open": statistics["open"],
        "done": statistics["done"],
    }


@app.get("/tasks/{task_id}", response_model=TaskRead)
def read_task(task_id: Annotated[int, PathParam(gt=0)]):
    task = _call_with_task_not_found_as_404(
        app.state.planner.get_task, task_id
    )
    return _task_read_data(task)


@app.put("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: Annotated[int, PathParam(gt=0)], payload: TaskUpdate
):
    task = _call_with_task_not_found_as_404(
        app.state.planner.replace_task,
        task_id,
        title=payload.title,
        priority=payload.priority,
        is_done=payload.is_done,
    )
    return _task_read_data(task)


@app.patch("/tasks/{task_id}", response_model=TaskRead)
def patch_task_endpoint(
    task_id: Annotated[int, PathParam(gt=0)], payload: TaskPatch
):
    changes = payload.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )
    task = _call_with_task_not_found_as_404(
        app.state.planner.patch_task, task_id, **changes
    )
    return _task_read_data(task)


@app.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_task_endpoint(task_id: Annotated[int, PathParam(gt=0)]):
    _call_with_task_not_found_as_404(app.state.planner.delete_task, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/tasks", status_code=status.HTTP_201_CREATED, response_model=TaskRead)
def create_task(payload: TaskCreate):
    try:
        task = app.state.planner.add_task(
            payload.title,
            priority=payload.priority,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return _task_read_data(task)
