from app.storage import MemoryStorage


def test_memory_storage_copies_containers_but_keeps_task_references(task):
    source = [task]
    storage = MemoryStorage(source)
    source.clear()

    loaded = storage.load()
    loaded.clear()

    stored = storage.load()
    assert stored == [task]
    assert stored[0] is task

    task.rename("Shared task")
    assert storage.load()[0].title == "Shared task"


def test_memory_storage_save_copies_the_container(task):
    storage = MemoryStorage()
    source = [task]

    storage.save(source)
    source.clear()

    loaded = storage.load()
    loaded.clear()

    assert storage.load() == [task]


def test_memory_storage_without_initial_tasks_starts_empty(memory_storage):
    assert memory_storage.load() == []
