from fastapi import FastAPI

from app.main import build_service
from app.routers.tasks.router import router as tasks_router


app = FastAPI(title="StudyHub Planner")
app.state.planner = build_service()
app.include_router(tasks_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/stats")
def read_stats():
    statistics = app.state.planner.get_statistics()
    return {
        "total": statistics["all"],
        "open": statistics["open"],
        "done": statistics["done"],
    }
