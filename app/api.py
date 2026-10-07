from fastapi import FastAPI, HTTPException, Query

from app.errors import TaskNotFoundError
from app.main import build_service


app = FastAPI(title="StudyHub Planner")
app.state.planner = build_service()


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/tasks")
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


@app.get("/tasks/{task_id}")
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
