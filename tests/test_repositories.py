import pytest

from app.errors import StorageError, TaskNotFoundError
from app.main import build_service
from app.models import Task
from app.repositories import JsonTaskRepository
from app.storage import JsonStorage, MemoryStorage


def test_json_repository_preserves_read_contracts(observed_storage, task):
    done_task = Task(2, "Read Python", 2, is_done=True, tags=["book"])
    observed_storage.inner.save([task, done_task])
    repository = JsonTaskRepository(observed_storage)

    assert repository.list() == [task, done_task]
    assert repository.get(2) == done_task
    assert repository.get(999) is None
    assert repository.select(is_done=False, sort_desc=True, limit=1) == [task]
    assert repository.search("  PYTHON ") == [task, done_task]
    assert repository.search("   ") == []
    assert repository.statistics() == {"all": 2, "open": 1, "done": 1}


def test_json_repository_loads_fresh_data_for_each_operation(
    observed_storage, task
):
    repository = JsonTaskRepository(observed_storage)
    assert observed_storage.load_calls == 0
    assert repository.list() == []
    assert observed_storage.load_calls == 1

    observed_storage.inner.save([task])
    assert repository.get(task.id) == task
    assert observed_storage.load_calls == 2


def test_json_repository_propagates_storage_errors():
    error = StorageError("read failed")

    class FailingStorage:
        def load(self):
            raise error

    repository = JsonTaskRepository(FailingStorage())

    with pytest.raises(StorageError) as caught:
        repository.list()

    assert caught.value is error


@pytest.mark.parametrize("task_id", [0, -1, True, "1"])
def test_service_validates_get_id_before_repository_read(
    task_id, planner_service, observed_storage
):
    with pytest.raises(ValueError):
        planner_service.get_task(task_id)

    assert observed_storage.load_calls == 0


def test_service_maps_missing_repository_result_to_domain_error(
    planner_service, observed_storage
):
    with pytest.raises(TaskNotFoundError, match="Задача с номером 999 не найдена"):
        planner_service.get_task(999)

    assert observed_storage.load_calls == 1


def test_service_reads_and_writes_through_the_same_json_storage(tmp_path):
    storage = JsonStorage(tmp_path / "tasks.json")
    service = build_service(storage=storage)

    assert service.storage is storage
    assert service.repository.storage is storage
    assert not storage.path.exists()

    added = service.add_task("Added through service", priority=3)
    assert service.list_tasks() == [added]

    external = Task(7, "Saved through the same storage", tags=["fresh"])
    storage.save([external])
    assert service.list_tasks() == [external]


def test_repository_can_read_empty_memory_storage():
    repository = JsonTaskRepository(MemoryStorage())

    assert repository.list() == []
    assert repository.statistics() == {"all": 0, "open": 0, "done": 0}
