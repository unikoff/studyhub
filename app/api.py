from fastapi import Depends, FastAPI

from app.core.config import load_settings
from app.core.dependencies import get_planner
from app.main import build_service
from app.routers.tasks.router import router as tasks_router
from app.services import PlannerService


settings = load_settings()
app = FastAPI(title=settings.app_name)
app.state.settings = settings
app.state.planner = build_service(settings=settings)
app.include_router(tasks_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/stats")
def read_stats(planner: PlannerService = Depends(get_planner)):
    statistics = planner.get_statistics()
    return {
        "total": statistics["all"],
        "open": statistics["open"],
        "done": statistics["done"],
    }
