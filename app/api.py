from fastapi import FastAPI

from app.DBase.engine import make_engine
from app.DBase.session import make_session_factory
from app.core.config import load_settings
from app.core.dependencies import PlannerDep
from app.routers.tasks.router import router as tasks_router
from app.routers.preferences.router import router as preferences_router


settings = load_settings()
app = FastAPI(title=settings.app_name)
app.state.settings = settings
app.state.engine = make_engine(settings.database_url)
app.state.session_factory = make_session_factory(app.state.engine)
app.include_router(tasks_router)
app.include_router(preferences_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/stats")
def read_stats(planner: PlannerDep):
    statistics = planner.get_statistics()
    return {
        "total": statistics["all"],
        "open": statistics["open"],
        "done": statistics["done"],
    }
