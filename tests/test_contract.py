import pytest


def _error_field(response):
    return response.json()["detail"][0]["loc"][-1]


@pytest.mark.parametrize(
    ("title", "expected_status", "expected_title"),
    [
        ("", 422, None),
        ("   ", 422, None),
        ("A", 201, "A"),
        ("A" * 120, 201, "A" * 120),
        ("A" * 121, 422, None),
        (" " + "A" * 120 + " ", 201, "A" * 120),
        (123, 422, None),
    ],
)
def test_post_title_boundaries(api_client, title, expected_status, expected_title):
    response = api_client.post(
        "/tasks", json={"title": title, "priority": 1}
    )

    assert response.status_code == expected_status
    if expected_status == 201:
        assert response.json()["title"] == expected_title
        assert response.json()["is_done"] is False
        assert set(response.json()) == {"id", "title", "priority", "is_done"}
    else:
        assert _error_field(response) == "title"


@pytest.mark.parametrize(
    ("priority", "expected_status"),
    [(1, 201), (5, 201), (0, 422), (6, 422), ("high", 422)],
)
def test_post_priority_boundaries(api_client, priority, expected_status):
    response = api_client.post(
        "/tasks", json={"title": "Valid title", "priority": priority}
    )

    assert response.status_code == expected_status
    if expected_status == 422:
        assert _error_field(response) == "priority"


@pytest.mark.parametrize("missing_field", ["title", "priority", "is_done"])
def test_put_requires_every_editable_field(api_client, api_service, missing_field):
    task = api_service.add_task("Keep", 3)
    payload = {"title": "Updated", "priority": 4, "is_done": False}
    payload.pop(missing_field)

    response = api_client.put(f"/tasks/{task.id}", json=payload)

    assert response.status_code == 422
    assert _error_field(response) == missing_field
    assert api_client.get(f"/tasks/{task.id}").json()["title"] == "Keep"


def test_put_keeps_resource_id(api_client, api_service):
    task = api_service.add_task("Before", 2)

    response = api_client.put(
        f"/tasks/{task.id}",
        json={"title": "After", "priority": 5, "is_done": True},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": task.id,
        "title": "After",
        "priority": 5,
        "is_done": True,
    }
    assert api_client.get(f"/tasks/{task.id}").json() == response.json()


@pytest.mark.parametrize("payload", [{}, {"title": None}])
def test_patch_omitted_and_null_fields_do_not_change_or_save(
    api_client, api_service, payload
):
    task = api_service.add_task("Keep", 3)
    path = f"/tasks/{task.id}"
    before_bytes = api_service.storage.path.read_bytes()
    before_task = api_client.get(path).json()

    response = api_client.patch(path, json=payload)

    assert response.status_code == 200
    assert response.json() == before_task
    assert api_service.storage.path.read_bytes() == before_bytes


def test_patch_applies_false_and_preserves_other_fields(api_client, api_service):
    task = api_service.add_task("Keep", 3)
    path = f"/tasks/{task.id}"

    response = api_client.patch(path, json={"is_done": False})

    assert response.status_code == 200
    assert response.json() == {
        "id": task.id,
        "title": "Keep",
        "priority": 3,
        "is_done": False,
    }
    assert api_client.get(path).json() == response.json()


def test_patch_rejects_invalid_title(api_client, api_service):
    task = api_service.add_task("Keep", 3)

    response = api_client.patch(f"/tasks/{task.id}", json={"title": "   "})

    assert response.status_code == 422
    assert _error_field(response) == "title"
    assert api_client.get(f"/tasks/{task.id}").json()["title"] == "Keep"


@pytest.mark.parametrize(
    ("method", "payload"),
    [
        ("post", {"title": "   ", "priority": 2}),
        ("put", {"title": "", "priority": 4, "is_done": True}),
        ("patch", {"title": ""}),
    ],
)
def test_invalid_write_keeps_task_stats_and_json_unchanged(
    api_client, api_service, method, payload
):
    task = api_service.add_task("Keep", 2)
    path = f"/tasks/{task.id}"
    before_task = api_client.get(path).json()
    before_stats = api_client.get("/stats").json()
    before_bytes = api_service.storage.path.read_bytes()
    request_path = "/tasks" if method == "post" else path

    response = getattr(api_client, method)(request_path, json=payload)

    assert response.status_code == 422
    assert api_client.get(path).json() == before_task
    assert api_client.get("/stats").json() == before_stats
    assert api_service.storage.path.read_bytes() == before_bytes


@pytest.mark.parametrize(
    ("method", "payload"),
    [
        ("get", None),
        ("put", {"title": "Missing", "priority": 2, "is_done": False}),
        ("patch", {"is_done": False}),
        ("delete", None),
    ],
)
def test_missing_valid_id_returns_404_without_upsert(
    api_client, api_service, method, payload
):
    existing = api_service.add_task("Existing", 2)
    missing_id = existing.id + 10
    before_bytes = api_service.storage.path.read_bytes()
    kwargs = {} if payload is None else {"json": payload}

    response = getattr(api_client, method)(f"/tasks/{missing_id}", **kwargs)

    assert response.status_code == 404
    assert api_service.storage.path.read_bytes() == before_bytes
    assert api_client.get("/tasks").json() == [
        {
            "id": existing.id,
            "title": "Existing",
            "priority": 2,
            "is_done": False,
        }
    ]


def test_unparseable_path_id_returns_422(api_client):
    response = api_client.get("/tasks/not-an-integer")

    assert response.status_code == 422
    assert _error_field(response) == "task_id"


@pytest.mark.parametrize("limit", [0, 51, "many"])
def test_invalid_limit_returns_422(api_client, limit):
    response = api_client.get("/tasks", params={"limit": limit})

    assert response.status_code == 422
    assert _error_field(response) == "limit"


def test_query_defaults_and_filter_sort_limit_do_not_change_source(
    api_client, api_service
):
    created = [
        api_service.add_task(f"Task {index}", 2) for index in range(12)
    ]
    api_service.mark_done(created[2].id)
    all_ids = [task.id for task in created]
    open_ids = [task.id for task in created if task.id != created[2].id]
    before_stats = api_client.get("/stats").json()
    before_bytes = api_service.storage.path.read_bytes()

    defaults = api_client.get("/tasks")
    assert [task["id"] for task in defaults.json()] == all_ids[:10]
    assert [task["id"] for task in api_client.get(
        "/tasks", params={"limit": 50}
    ).json()] == all_ids
    assert [task["id"] for task in api_client.get(
        "/tasks", params={"is_done": False, "sort_desc": True, "limit": 1}
    ).json()] == sorted(open_ids, reverse=True)[:1]
    assert [task["id"] for task in api_client.get(
        "/tasks", params={"is_done": True, "sort_desc": False}
    ).json()] == [created[2].id]
    assert [task["id"] for task in api_client.get(
        "/tasks", params={"sort_desc": True, "limit": 1}
    ).json()] == sorted(all_ids, reverse=True)[:1]
    assert api_client.get("/stats").json() == before_stats
    assert api_service.storage.path.read_bytes() == before_bytes


@pytest.mark.parametrize("limit", [1, 50])
def test_limit_inclusive_boundaries_are_valid(api_client, limit):
    response = api_client.get("/tasks", params={"limit": limit})

    assert response.status_code == 200


def test_openapi_documents_current_contract(api_client):
    response = api_client.get("/openapi.json")
    assert response.status_code == 200
    document = response.json()
    schemas = document["components"]["schemas"]

    assert set(schemas["TaskCreate"]["required"]) == {"title", "priority"}
    assert set(schemas["TaskUpdate"]["required"]) == {
        "title", "priority", "is_done"
    }
    assert set(schemas["TaskRead"]["required"]) == {
        "id", "title", "priority", "is_done"
    }
    assert schemas["TaskPatch"].get("required", []) == []
    assert "201" in document["paths"]["/tasks"]["post"]["responses"]
    assert "204" in document["paths"]["/tasks/{task_id}"]["delete"]["responses"]

    list_operation = document["paths"]["/tasks"]["get"]
    list_parameters = {
        parameter["name"]: parameter
        for parameter in list_operation["parameters"]
    }
    assert set(list_parameters) == {"is_done", "sort_desc", "limit"}
    assert list_parameters["is_done"]["required"] is False
    assert list_parameters["sort_desc"]["schema"]["default"] is False
    assert list_parameters["limit"]["schema"]["default"] == 10
    assert list_parameters["limit"]["schema"]["minimum"] == 1
    assert list_parameters["limit"]["schema"]["maximum"] == 50

    item_parameters = document["paths"]["/tasks/{task_id}"]["get"]["parameters"]
    assert [parameter["name"] for parameter in item_parameters] == ["task_id"]
    assert item_parameters[0]["required"] is True
    assert item_parameters[0]["schema"]["exclusiveMinimum"] == 0

    for operations in document["paths"].values():
        for operation in operations.values():
            assert "planner" not in {
                parameter["name"] for parameter in operation.get("parameters", [])
            }

    put_body = document["paths"]["/tasks/{task_id}"]["put"]["requestBody"]
    patch_body = document["paths"]["/tasks/{task_id}"]["patch"]["requestBody"]
    assert put_body["required"] is True
    assert put_body["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/TaskUpdate"
    )
    assert patch_body["required"] is True
    assert patch_body["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/TaskPatch"
    )
