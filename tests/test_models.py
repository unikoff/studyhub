import pytest

from app.models import Task


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("id", True, "id должен быть целым числом"),
        ("id", 0, "Номер задачи должен быть положительным"),
        ("title", None, "Название должно быть строкой"),
        ("title", "   ", "Название не может быть пустым"),
        ("priority", True, "priority должен быть целым числом"),
        ("priority", 0, "Приоритет должен быть от 1 до 5"),
        ("priority", 6, "Приоритет должен быть от 1 до 5"),
        ("is_done", 1, "is_done должен быть bool"),
        ("tags", None, "Метки должны быть списком"),
        ("tags", [1], "Каждая метка должна быть строкой"),
        ("tags", ["  "], "Метка не может быть пустой"),
    ],
)
def test_task_rejects_invalid_fields(field, value, message):
    values = {
        "id": 1,
        "title": "Python",
        "priority": 2,
        "is_done": False,
        "tags": [],
    }
    values[field] = value

    with pytest.raises(ValueError) as error:
        Task(**values)

    assert str(error.value) == message


@pytest.mark.parametrize("priority", [1, 5])
def test_task_accepts_priority_boundaries(priority):
    assert Task(1, "Python", priority).priority == priority


def test_each_task_gets_independent_tags():
    first = Task(1, "First")
    second = Task(2, "Second")

    first.tags.append("python")

    assert first.tags == ["python"]
    assert second.tags == []
    assert first.tags is not second.tags


def test_task_normalizes_title_and_copies_normalized_tags():
    source_tags = [" python ", " testing "]

    task = Task(1, "  Learn Python  ", tags=source_tags)
    source_tags.append("outside")

    assert task.title == "Learn Python"
    assert task.priority == 2
    assert task.is_done is False
    assert task.tags == ["python", "testing"]


@pytest.mark.parametrize(
    ("method_name", "invalid_value", "attribute", "original_value"),
    [
        ("rename", "   ", "title", "Python"),
        ("set_priority", 6, "priority", 3),
    ],
)
def test_task_mutators_validate_before_changing_state(
    task, method_name, invalid_value, attribute, original_value
):
    method = getattr(task, method_name)

    with pytest.raises(ValueError):
        method(invalid_value)

    assert getattr(task, attribute) == original_value


def test_task_status_and_mark_done_are_consistent(task):
    assert task.status_label == "не завершена"

    task.mark_done()
    task.mark_done()

    assert task.is_done is True
    assert task.status_label == "выполнена"
    assert "выполнена" in str(task)


def test_task_to_dict_returns_a_separate_tags_list(task):
    record = task.to_dict()
    record["tags"].append("external")

    assert task.tags == ["study"]


@pytest.mark.parametrize(
    ("record", "expected_tags"),
    [
        (
            {"id": 7, "title": "Old task", "priority": 4, "is_done": True},
            [],
        ),
        (
            {
                "id": 8,
                "title": "Tagged task",
                "priority": 2,
                "is_done": False,
                "tags": ["python"],
            },
            ["python"],
        ),
    ],
)
def test_task_from_dict_accepts_current_and_legacy_records(record, expected_tags):
    task = Task.from_dict(record)

    assert task.id == record["id"]
    assert task.tags == expected_tags
    assert task.to_dict()["tags"] == expected_tags


def test_task_from_dict_rejects_a_non_mapping():
    with pytest.raises(ValueError, match="Запись задачи должна быть словарём"):
        Task.from_dict(["not", "a", "record"])
