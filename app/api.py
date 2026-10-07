from fastapi import FastAPI, HTTPException, Query, status

from app.errors import TaskNotFoundError
from app.main import build_service
from app.schemas import TaskCreate, TaskPatch, TaskRead, TaskUpdate


app = FastAPI(title="StudyHub Planner")
app.state.planner = build_service()


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
    return [
        {
            "id": task.id,
            "title": task.title,
            "priority": task.priority,
            "is_done": task.is_done,
        }
        for task in tasks
    ]


@app.get("/stats")
def read_stats():
    statistics = app.state.planner.get_statistics()
    return {
        "total": statistics["all"],
        "open": statistics["open"],
        "done": statistics["done"],
    }


@app.get("/tasks/{task_id}", response_model=TaskRead)
def read_task(task_id: int):
    try:
        task = app.state.planner.get_task(task_id)
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        ) from error
    return {
        "id": task.id,
        "title": task.title,
        "priority": task.priority,
        "is_done": task.is_done,
    }


@app.put("/tasks/{task_id}", response_model=TaskRead)
def update_task(task_id: int, payload: TaskUpdate):
    try:
        return app.state.planner.replace_task(
            task_id,
            title=payload.title,
            priority=payload.priority,
            is_done=payload.is_done,
        )
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        ) from error


@app.patch("/tasks/{task_id}", response_model=TaskRead)
def patch_task_endpoint(task_id: int, payload: TaskPatch):
    changes = payload.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )
    try:
        return app.state.planner.patch_task(task_id, **changes)
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        ) from error


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

    return {
        "id": task.id,
        "title": task.title,
        "priority": task.priority,
        "is_done": task.is_done,
    }
