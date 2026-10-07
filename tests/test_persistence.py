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


def test_legacy_json_without_tags_loads_as_an_untagged_task(tmp_path):
    path = tmp_path / "legacy.json"
    original = '[{"id": 4, "title": "Old task", "priority": 3, "is_done": true}]'
    path.write_text(original, encoding="utf-8")

    tasks = JsonStorage(path).load()

    assert len(tasks) == 1
    assert tasks[0].id == 4
    assert tasks[0].title == "Old task"
    assert tasks[0].is_done is True
    assert tasks[0].tags == []
    assert path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize(
    "contents",
    [
        "{}",
        '[{"id": 1, "title": "Task", "priority": 2, "is_done": 1}]',
        (
            '[{"id": 1, "title": "First", "priority": 2, "is_done": false},'
            ' {"id": 1, "title": "Second", "priority": 3, "is_done": false}]'
        ),
    ],
)
def test_invalid_json_schema_raises_without_rewriting_file(tmp_path, contents):
    path = tmp_path / "invalid.json"
    path.write_text(contents, encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(StorageError):
        JsonStorage(path).load()

    assert path.read_bytes() == before


def test_reading_a_directory_as_json_raises_storage_error(tmp_path):
    path = tmp_path / "directory"
    path.mkdir()

    with pytest.raises(StorageError):
        JsonStorage(path).load()


def test_unwritable_parent_raises_storage_error_without_changing_it(tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("keep", encoding="utf-8")
    before = blocker.read_bytes()
    path = blocker / "tasks.json"

    with pytest.raises(StorageError):
        JsonStorage(path).save([])

    assert blocker.read_bytes() == before


def test_invalid_snapshot_does_not_overwrite_existing_json(tmp_path, task):
    path = tmp_path / "tasks.json"
    path.write_text("previous data", encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(StorageError):
        JsonStorage(path).save([task, object()])

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


def test_select_tasks_does_not_change_full_planner(tmp_path):
    from app.models import Task

    path = tmp_path / "tasks.json"
    original = [
        Task(id=2, title="CLI", priority=2, is_done=False, tags=["terminal"]),
        Task(id=7, title="HTTP", priority=4, is_done=True, tags=["api"]),
        Task(id=11, title="Tests", priority=3, is_done=False, tags=["pytest"]),
    ]
    JsonStorage(path).save(original)
    service = PlannerService(JsonStorage(path))

    selected = service.select_tasks(is_done=False, sort_desc=True, limit=1)

    reader = PlannerService(JsonStorage(path))
    assert [task.id for task in selected] == [11]
    assert [task.id for task in reader.list_tasks()] == [2, 7, 11]
    assert reader.get_statistics() == {"all": 3, "open": 2, "done": 1}
    assert JsonStorage(path).load() == original


def test_replace_and_patch_save_validated_tasks_without_losing_tags(tmp_path):
    from app.models import Task

    path = tmp_path / "tasks.json"
    storage = JsonStorage(path)
    original = Task(
        id=4,
        title="Original",
        priority=2,
        is_done=False,
        tags=["keep"],
    )
    storage.save([original])
    service = PlannerService(JsonStorage(path))

    replaced = service.replace_task(
        4,
        title="  Replaced  ",
        priority=5,
        is_done=True,
    )
    after_put = PlannerService(JsonStorage(path)).get_task(4)
    assert (replaced.id, replaced.title, replaced.priority, replaced.is_done) == (
        4,
        "Replaced",
        5,
        True,
    )
    assert after_put.tags == ["keep"]

    patched = service.patch_task(4, is_done=False)
    reader = PlannerService(JsonStorage(path))
    restored = reader.get_task(4)
    assert patched.is_done is False
    assert (restored.id, restored.title, restored.priority, restored.is_done) == (
        4,
        "Replaced",
        5,
        False,
    )
    assert restored.tags == ["keep"]
    assert reader.get_statistics() == {"all": 1, "open": 1, "done": 0}

    before_noop = path.read_bytes()
    unchanged = service.patch_task(4)
    assert unchanged == restored
    assert path.read_bytes() == before_noop


def test_failed_updates_do_not_save_or_create_missing_tasks(tmp_path):
    from app.models import Task

    path = tmp_path / "tasks.json"
    storage = JsonStorage(path)
    storage.save([Task(id=6, title="Keep", priority=3, tags=["original"])])
    service = PlannerService(JsonStorage(path))
    before = path.read_bytes()

    with pytest.raises(ValueError):
        service.replace_task(6, title="   ", priority=5, is_done=False)
    assert path.read_bytes() == before

    with pytest.raises(ValueError):
        service.patch_task(6, title="   ")
    assert path.read_bytes() == before

    with pytest.raises(TaskNotFoundError):
        service.replace_task(999, title="Missing", priority=2, is_done=False)
    assert path.read_bytes() == before

    with pytest.raises(TaskNotFoundError):
        service.patch_task(999, is_done=False)
    assert path.read_bytes() == before
