import pytest

from app.errors import TaskNotFoundError
from app.models import Task


def test_reads_and_statistics_use_current_tasks_without_saving(
    task, observed_storage, planner_service
):
    done_task = Task(2, "Read Python", 2, is_done=True, tags=["book"])
    observed_storage.inner.save([task, done_task])
    observed_storage.save_calls = 0

    assert planner_service.list_tasks() == [task, done_task]
    assert planner_service.get_task(1) is task
    assert planner_service.search_tasks("  PYTHON ") == [task, done_task]
    assert planner_service.search_tasks("   ") == []
    assert planner_service.get_statistics() == {"all": 2, "open": 1, "done": 1}
    assert observed_storage.save_calls == 0


def test_add_task_uses_next_id_copies_tags_and_saves_once(
    observed_storage, planner_service
):
    observed_storage.inner.save([Task(4, "Existing", 2)])
    observed_storage.save_calls = 0
    tags = [" python "]

    added = planner_service.add_task(" New task ", 5, tags=tags)
    tags.append("outside")

    assert added.id == 5
    assert added.title == "New task"
    assert added.tags == ["python"]
    assert [item.id for item in observed_storage.inner.load()] == [4, 5]
    assert observed_storage.save_calls == 1


@pytest.mark.parametrize(
    ("title", "priority"),
    [
        ("   ", 2),
        ("New task", 6),
    ],
)
def test_invalid_add_leaves_storage_unchanged(
    title, priority, task, observed_storage, planner_service
):
    observed_storage.inner.save([task])
    observed_storage.save_calls = 0
    before = [item.to_dict() for item in observed_storage.inner.load()]

    with pytest.raises(ValueError):
        planner_service.add_task(title, priority)

    assert [item.to_dict() for item in observed_storage.inner.load()] == before
    assert observed_storage.save_calls == 0


def test_mark_done_saves_once_and_repeated_done_is_idempotent(
    task, observed_storage, planner_service
):
    observed_storage.inner.save([task])
    observed_storage.save_calls = 0

    first = planner_service.mark_done(task.id)
    second = planner_service.mark_done(task.id)

    assert first is task
    assert second is task
    assert task.is_done is True
    assert observed_storage.save_calls == 1


def test_delete_task_removes_existing_task_and_saves_once(
    task, observed_storage, planner_service
):
    observed_storage.inner.save([task])
    observed_storage.save_calls = 0

    result = planner_service.delete_task(task.id)

    assert result is None
    assert observed_storage.inner.load() == []
    assert observed_storage.save_calls == 1


@pytest.mark.parametrize("action", ["mark_done", "delete_task"])
def test_unknown_id_does_not_change_storage_or_save(
    action, task, observed_storage, planner_service
):
    observed_storage.inner.save([task])
    observed_storage.save_calls = 0
    before = [item.to_dict() for item in observed_storage.inner.load()]

    with pytest.raises(TaskNotFoundError):
        getattr(planner_service, action)(999)

    assert [item.to_dict() for item in observed_storage.inner.load()] == before
    assert observed_storage.save_calls == 0


@pytest.mark.parametrize(
    ("is_done", "expected_ids"),
    [
        (None, [1, 2, 3]),
        (False, [1, 3]),
        (True, [2]),
    ],
)
def test_select_tasks_filters_and_sorts_by_id(
    is_done, expected_ids, observed_storage, planner_service
):
    observed_storage.inner.save(
        [
            Task(3, "Third", 2, tags=["three"]),
            Task(2, "Second", 3, is_done=True, tags=["two"]),
            Task(1, "First", 1, tags=["one"]),
        ]
    )

    selected = planner_service.select_tasks(is_done=is_done)

    assert [item.id for item in selected] == expected_ids
    assert [item.id for item in planner_service.select_tasks(sort_desc=True)] == [
        3, 2, 1
    ]


def test_select_tasks_applies_limit_after_filter_and_sort(
    observed_storage, planner_service
):
    observed_storage.inner.save(
        [
            Task(8, "Done", 2, is_done=True),
            Task(5, "Open five", 3),
            Task(2, "Open two", 4),
            Task(1, "Done one", 1, is_done=True),
        ]
    )

    selected = planner_service.select_tasks(
        is_done=False, sort_desc=True, limit=1
    )

    assert [item.id for item in selected] == [5]


def test_replace_and_patch_preserve_identity_and_tags_and_apply_false(
    observed_storage, planner_service
):
    original = Task(4, "Original", 2, is_done=True, tags=["keep"])
    observed_storage.inner.save([original])
    observed_storage.save_calls = 0

    replaced = planner_service.replace_task(
        4, title=" Updated ", priority=5, is_done=False
    )
    patched = planner_service.patch_task(4, is_done=False)

    assert (replaced.id, replaced.title, replaced.priority, replaced.is_done) == (
        4,
        "Updated",
        5,
        False,
    )
    assert replaced.tags == ["keep"]
    assert patched.id == 4
    assert patched.tags == ["keep"]
    assert patched.is_done is False
    assert observed_storage.save_calls == 2


def test_patch_with_no_fields_or_none_does_not_change_or_save(
    observed_storage, planner_service
):
    original = Task(1, "Keep", 3, tags=["keep"])
    observed_storage.inner.save([original])
    observed_storage.save_calls = 0
    before = original.to_dict()

    assert planner_service.patch_task(1) == original
    assert planner_service.patch_task(1, is_done=None) == original
    assert original.to_dict() == before
    assert observed_storage.save_calls == 0


def test_failed_replace_does_not_save_or_change_existing_task(
    observed_storage, planner_service
):
    original = Task(1, "Keep", 2, tags=["keep"])
    observed_storage.inner.save([original])
    observed_storage.save_calls = 0
    before = original.to_dict()

    with pytest.raises(ValueError):
        planner_service.replace_task(1, title="  ", priority=2, is_done=False)

    assert original.to_dict() == before
    assert observed_storage.save_calls == 0


def test_failed_patch_does_not_save_or_change_existing_task(
    observed_storage, planner_service
):
    original = Task(1, "Keep", 2, tags=["keep"])
    observed_storage.inner.save([original])
    observed_storage.save_calls = 0
    before = original.to_dict()

    with pytest.raises(ValueError):
        planner_service.patch_task(1, title="  ")

    assert original.to_dict() == before
    assert observed_storage.save_calls == 0
