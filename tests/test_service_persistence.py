from app.main import build_service
from app.models import Task
from app.storage import JsonStorage


def test_add_task_uses_empty_and_gapped_ids_and_persists_full_task(tmp_path):
    empty_path = tmp_path / "empty.json"
    empty_service = build_service(JsonStorage(empty_path))

    first = empty_service.add_task("First", priority=3)

    assert first.id == 1
    assert first.is_done is False
    assert first.tags == []
    assert build_service(JsonStorage(empty_path)).list_tasks() == [first]

    gapped_path = tmp_path / "gapped.json"
    JsonStorage(gapped_path).save(
        [
            Task(2, "CLI", 2, tags=["terminal"]),
            Task(7, "HTTP", 4, is_done=True, tags=["api"]),
        ]
    )
    gapped_service = build_service(JsonStorage(gapped_path))

    created = gapped_service.add_task("Tests", priority=3)

    assert created.id == 8
    assert created.is_done is False
    assert created.tags == []
    loaded = build_service(JsonStorage(gapped_path)).list_tasks()
    assert [task.id for task in loaded] == [2, 7, 8]
    assert loaded[-1] == created


def test_service_reads_and_selection_do_not_rewrite_json(tmp_path):
    path = tmp_path / "tasks.json"
    JsonStorage(path).save(
        [
            Task(2, "CLI", 2, tags=["terminal"]),
            Task(7, "HTTP", 4, is_done=True, tags=["api"]),
            Task(11, "Tests", 3, tags=["pytest"]),
        ]
    )
    service = build_service(JsonStorage(path))
    before = path.read_bytes()

    assert [task.id for task in service.list_tasks()] == [2, 7, 11]
    assert service.get_task(7).tags == ["api"]
    assert [task.id for task in service.select_tasks(
        is_done=False, sort_desc=True, limit=1
    )] == [11]
    assert service.get_statistics() == {"all": 3, "open": 2, "done": 1}
    assert path.read_bytes() == before
    assert [task.id for task in build_service(JsonStorage(path)).list_tasks()] == [
        2, 7, 11
    ]


def test_replace_and_patch_persist_full_tasks_and_keep_neighbors(tmp_path):
    path = tmp_path / "tasks.json"
    JsonStorage(path).save(
        [
            Task(7, "HTTP", 4, is_done=True, tags=["api"]),
            Task(11, "Neighbor", 2, tags=["keep"]),
        ]
    )
    service = build_service(JsonStorage(path))

    patched = service.patch_task(7, is_done=False)
    assert patched.id == 7
    assert patched.is_done is False

    after_patch = build_service(JsonStorage(path)).list_tasks()
    saved_patch = next(task for task in after_patch if task.id == 7)
    assert saved_patch.is_done is False
    assert saved_patch.tags == ["api"]

    replaced = service.replace_task(
        7, title="HTTP tests", priority=1, is_done=True
    )
    assert replaced.id == 7
    assert replaced.title == "HTTP tests"

    reloaded = build_service(JsonStorage(path)).list_tasks()
    updated = next(task for task in reloaded if task.id == 7)
    neighbor = next(task for task in reloaded if task.id == 11)
    assert (updated.id, updated.title, updated.priority, updated.is_done) == (
        7, "HTTP tests", 1, True
    )
    assert updated.tags == ["api"]
    assert (neighbor.id, neighbor.tags) == (11, ["keep"])


def test_delete_persists_only_target_removal(tmp_path):
    path = tmp_path / "tasks.json"
    JsonStorage(path).save(
        [
            Task(2, "Keep first", tags=["one"]),
            Task(7, "Delete me", tags=["remove"]),
            Task(11, "Keep last", tags=["last"]),
        ]
    )
    service = build_service(JsonStorage(path))

    service.delete_task(7)

    reloaded = build_service(JsonStorage(path)).list_tasks()
    assert [(task.id, task.tags) for task in reloaded] == [
        (2, ["one"]),
        (11, ["last"]),
    ]
