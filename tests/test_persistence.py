import json

import pytest

from app.errors import StorageError, TaskNotFoundError
from app.services import PlannerService
from app.storage import JsonStorage


def test_tasks_survive_service_restart_and_keep_ids(tmp_path):
    path = tmp_path / "nested" / "tasks.json"
    first_service = PlannerService(JsonStorage(path))

    first = first_service.add_task("First", 3, tags=["study"])
    second = first_service.add_task("Second", 2)
    first_service.mark_done(first.id)
    first_service.delete_task(second.id)

    restarted = PlannerService(JsonStorage(path))
    restored = restarted.list_tasks()
    assert [(task.id, task.title, task.is_done, task.tags) for task in restored] == [
        (1, "First", True, ["study"]),
    ]
    next_task = restarted.add_task("After restart", 1)
    assert next_task.id == 2
    assert [task.id for task in restarted.list_tasks()] == [1, 2]

    records = json.loads(path.read_text(encoding="utf-8"))
    assert records[0]["tags"] == ["study"]
    assert records[0]["is_done"] is True


def test_missing_file_is_empty_until_first_change(tmp_path):
    path = tmp_path / "new" / "tasks.json"
    service = PlannerService(JsonStorage(path))

    assert service.list_tasks() == []
    assert not path.exists()

    service.add_task("First", 2)
    assert path.exists()
    assert len(PlannerService(JsonStorage(path)).list_tasks()) == 1


def test_unknown_id_does_not_change_json(tmp_path):
    path = tmp_path / "tasks.json"
    service = PlannerService(JsonStorage(path))
    service.add_task("Keep", 2)
    before = path.read_bytes()

    with pytest.raises(TaskNotFoundError):
        service.delete_task(999)

    assert path.read_bytes() == before


def test_malformed_json_raises_storage_error_without_rewrite(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text("{broken", encoding="utf-8")
    before = path.read_bytes()
    service = PlannerService(JsonStorage(path))

    with pytest.raises(StorageError):
        service.list_tasks()

    assert path.read_bytes() == before


def test_added_task_uses_max_id_and_full_task_survives_new_service(tmp_path):
    from app.models import Task

    path = tmp_path / "tasks.json"
    storage = JsonStorage(path)
    storage.save(
        [
            Task(id=2, title="HTTP", priority=3, tags=["existing"]),
            Task(
                id=7,
                title="JSON",
                priority=4,
                is_done=True,
                tags=["keep"],
            ),
        ]
    )

    first_service = PlannerService(storage)
    created = first_service.add_task("Planner API", priority=5)

    second_service = PlannerService(JsonStorage(path))
    loaded = second_service.list_tasks()

    assert created.id == 8
    assert [
        (task.id, task.title, task.priority, task.is_done, task.tags)
        for task in loaded
    ] == [
        (2, "HTTP", 3, False, ["existing"]),
        (7, "JSON", 4, True, ["keep"]),
        (8, "Planner API", 5, False, []),
    ]
