import pytest


def test_preferences_returns_default_when_client_version_is_missing(api_client):
    response = api_client.get("/preferences")

    assert response.status_code == 200
    assert response.json() == {"view": "compact", "client_version": None}
    assert response.headers["X-Planner-Version"] == "1"
    assert "X-Client-Version" not in response.headers


@pytest.mark.parametrize(
    ("client_version", "expected"),
    [
        pytest.param("2.4.1", "2.4.1", id="ordinary-value"),
        pytest.param("", "", id="empty-value"),
        pytest.param("v" * 64, "v" * 64, id="maximum-length"),
    ],
)
def test_preferences_preserves_client_version_in_body(
    api_client, client_version, expected
):
    response = api_client.get(
        "/preferences",
        headers={"X-Client-Version": client_version},
    )

    assert response.status_code == 200
    assert response.json() == {
        "view": "compact",
        "client_version": expected,
    }
    assert response.headers["X-Planner-Version"] == "1"
    assert "X-Client-Version" not in response.headers


def test_preferences_requests_do_not_change_tasks_or_storage(
    api_client, api_service
):
    task = api_service.add_task("Keep task unchanged", 3)
    before = api_service.storage.path.read_bytes()

    successful = api_client.get(
        "/preferences",
        headers={"X-Client-Version": "1.0"},
    )
    assert successful.status_code == 200
    assert successful.json() == {"view": "compact", "client_version": "1.0"}
    assert successful.headers["X-Planner-Version"] == "1"
    assert api_service.storage.path.read_bytes() == before

    response = api_client.get(
        "/preferences",
        headers={"X-Client-Version": "v" * 65},
    )

    assert response.status_code == 422
    assert "X-Planner-Version" not in response.headers
    assert api_service.storage.path.read_bytes() == before
    assert api_client.get(f"/tasks/{task.id}").json() == {
        "id": task.id,
        "title": "Keep task unchanged",
        "priority": 3,
        "is_done": False,
    }
    assert api_client.get("/stats").json() == {
        "total": 1,
        "open": 1,
        "done": 0,
    }
