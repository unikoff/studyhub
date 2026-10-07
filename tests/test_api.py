import pytest

def public_task(task):
    return {
        "id": task.id,
        "title": task.title,
        "priority": task.priority,
        "is_done": task.is_done,
    }


def test_health_and_empty_state(api_client):
    health = api_client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert api_client.get("/tasks").json() == []
    assert api_client.get("/stats").json() == {"total": 0, "open": 0, "done": 0}


def test_list_and_stats_use_seeded_api_state(api_client, api_service):
    first = api_service.add_task("Open task", 2, tags=["api-test"])
    second = api_service.add_task("Done task", 4, tags=["keep"])
    api_service.mark_done(second.id)

    listed = api_client.get("/tasks", params={"is_done": False, "limit": 1})

    assert listed.status_code == 200
    assert listed.json() == [public_task(first)]
    assert api_client.get("/stats").json() == {"total": 2, "open": 1, "done": 1}


def test_create_then_read_uses_server_id_and_public_schema(api_client):
    response = api_client.post("/tasks", json={"title": "Read", "priority": 2})
    assert response.status_code == 201
    created = response.json()
    assert set(created) == {"id", "title", "priority", "is_done"}
    assert created["is_done"] is False
    assert api_client.get(f"/tasks/{created['id']}").json() == created


def test_read_returns_public_task_without_tags(api_client, api_service):
    task = api_service.add_task("Visible task", 3, tags=["internal"])

    response = api_client.get(f"/tasks/{task.id}")

    assert response.status_code == 200
    assert response.json() == public_task(task)
    assert "tags" not in response.json()


@pytest.mark.parametrize(
    ("method", "body"),
    [
        ("get", None),
        ("put", {"title": "Updated", "priority": 3, "is_done": False}),
        ("patch", {"is_done": False}),
        ("delete", None),
    ],
)
def test_missing_positive_id_returns_404_without_changing_json(
    api_client, api_service, method, body
):
    api_service.add_task("Keep", 2)
    path = api_service.storage.path
    before = path.read_bytes()

    response = getattr(api_client, method)(
        "/tasks/999", **({} if body is None else {"json": body})
    )

    assert response.status_code == 404
    assert path.read_bytes() == before


@pytest.mark.parametrize("task_id", [0, -1])
@pytest.mark.parametrize(
    ("method", "body"),
    [
        ("get", None),
        ("put", {"title": "Updated", "priority": 3, "is_done": False}),
        ("patch", {"is_done": False}),
        ("delete", None),
    ],
)
def test_nonpositive_ids_return_422_without_changing_json(
    api_client, api_service, task_id, method, body
):
    api_service.add_task("Keep", 2)
    path = api_service.storage.path
    before = path.read_bytes()

    response = getattr(api_client, method)(
        f"/tasks/{task_id}", **({} if body is None else {"json": body})
    )

    assert response.status_code == 422
    assert path.read_bytes() == before


def test_non_integer_id_is_422_without_creating_json(api_client, api_service):
    response = api_client.get("/tasks/not-an-int")

    assert response.status_code == 422
    assert not api_service.storage.path.exists()


def test_put_and_patch_preserve_id_tags_and_explicit_false(api_client, api_service):
    original = api_service.add_task("Draft", 1, tags=["keep"])
    path = f"/tasks/{original.id}"

    put = api_client.put(
        path, json={"title": "Review", "priority": 4, "is_done": True}
    )
    assert put.status_code == 200
    assert put.json() == {
        "id": original.id,
        "title": "Review",
        "priority": 4,
        "is_done": True,
    }
    after_put = api_service.get_task(original.id)
    assert after_put.id == original.id
    assert after_put.tags == ["keep"]

    patch = api_client.patch(path, json={"is_done": False})
    assert patch.status_code == 200
    assert patch.json()["is_done"] is False
    after_patch = api_service.get_task(original.id)
    assert after_patch.id == original.id
    assert after_patch.tags == ["keep"]
    assert after_patch.title == "Review"


def test_empty_and_null_patch_do_not_change_or_save(api_client, api_service):
    task = api_service.add_task("Keep", 2, tags=["tag"])
    path = f"/tasks/{task.id}"
    before_data = api_service.storage.path.read_bytes()
    expected = public_task(task)

    empty = api_client.patch(path, json={})
    explicit_null = api_client.patch(path, json={"title": None})

    assert empty.status_code == explicit_null.status_code == 200
    assert empty.json() == explicit_null.json() == expected
    assert api_service.storage.path.read_bytes() == before_data


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/tasks", {"title": "   ", "priority": 2}),
        ("put", "/tasks/1", {"title": "", "priority": 2, "is_done": False}),
        ("patch", "/tasks/1", {"priority": 99}),
    ],
)
def test_invalid_payload_does_not_change_state(
    api_client, api_service, method, path, body
):
    task = api_service.add_task("Keep", 2, tags=["tag"])
    if path.endswith("/1"):
        path = f"/tasks/{task.id}"
    before_data = api_service.storage.path.read_bytes()
    before_tasks = api_client.get("/tasks").json()
    before_stats = api_client.get("/stats").json()

    response = getattr(api_client, method)(path, json=body)

    assert response.status_code == 422
    assert api_service.storage.path.read_bytes() == before_data
    assert api_client.get("/tasks").json() == before_tasks
    assert api_client.get("/stats").json() == before_stats


def test_delete_returns_empty_204_then_get_and_repeat_delete_return_404(
    api_client, api_service
):
    task = api_service.add_task("Temporary", 1)
    path = f"/tasks/{task.id}"

    response = api_client.delete(path)

    assert response.status_code == 204
    assert response.content == b""
    assert api_client.get(path).status_code == 404
    repeated = api_client.delete(path)
    assert repeated.status_code == 404
    assert repeated.json() == {"detail": "Task not found"}


def test_scenarios_do_not_use_the_project_data_file(api_service, tmp_path):
    assert api_service.storage.path == tmp_path / "tasks.json"
