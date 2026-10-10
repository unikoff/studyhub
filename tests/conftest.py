import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.core.dependencies import get_planner
from app.main import build_service
from app.storage import JsonStorage

from app.models import Task
from app.services import PlannerService
from app.storage import MemoryStorage


class ObservedStorage:
    def __init__(self, inner):
        self.inner = inner
        self.load_calls = 0
        self.save_calls = 0

    def load(self):
        self.load_calls += 1
        return self.inner.load()

    def save(self, tasks):
        self.save_calls += 1
        self.inner.save(tasks)


@pytest.fixture
def task():
    return Task(1, "Python", 3, tags=["study"])


@pytest.fixture
def memory_storage():
    return MemoryStorage()


@pytest.fixture
def observed_storage(memory_storage):
    return ObservedStorage(memory_storage)


@pytest.fixture
def planner_service(observed_storage):
    return PlannerService(observed_storage)


@pytest.fixture
def api_service(tmp_path):
    return build_service(JsonStorage(tmp_path / "tasks.json"))


@pytest.fixture
def api_client(api_service):
    previous_overrides = app.dependency_overrides.copy()

    def get_test_planner():
        return api_service

    app.dependency_overrides[get_planner] = get_test_planner
    try:
        with TestClient(app, follow_redirects=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
