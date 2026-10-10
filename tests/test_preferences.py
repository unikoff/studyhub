import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.cli import run
from app.core.config import Settings
from app.core.dependencies import get_settings


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


@pytest.mark.parametrize(
    ("cookie_secure", "base_url"),
    [
        pytest.param(False, "http://testserver", id="local-http"),
        pytest.param(True, "https://testserver", id="configured-https"),
    ],
)
def test_cookie_secure_policy_comes_from_settings(
    tmp_path, cookie_secure, base_url
):
    settings = Settings(
        json_path=tmp_path / "tasks.json",
        app_name="Test Planner",
        cookie_secure=cookie_secure,
    )
    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        with TestClient(
            app,
            base_url=base_url,
            follow_redirects=False,
        ) as client:
            selected = client.put(
                "/preferences",
                json={"view": "detailed"},
                headers={"X-Client-Version": "policy-test"},
            )
            assert selected.status_code == 200
            assert selected.json() == {
                "view": "detailed",
                "client_version": "policy-test",
            }
            assert selected.headers["X-Planner-Version"] == "1"

            set_cookie = selected.headers["set-cookie"].lower()
            assert "planner_view=detailed" in set_cookie
            assert "path=/preferences" in set_cookie
            assert "httponly" in set_cookie
            assert "samesite=lax" in set_cookie
            assert ("secure" in set_cookie) is cookie_secure
            assert "domain=" not in set_cookie
            assert "expires=" not in set_cookie
            assert "max-age=" not in set_cookie

            assert client.cookies.get("planner_view") == "detailed"
            assert client.get("/preferences").json()["view"] == "detailed"

            deleted = client.delete("/preferences")
            assert deleted.status_code == 204
            assert deleted.content == b""
            assert deleted.headers["X-Planner-Version"] == "1"
            deletion = deleted.headers["set-cookie"].lower()
            assert "planner_view=" in deletion
            assert "path=/preferences" in deletion
            assert "max-age=0" in deletion
            assert "httponly" in deletion
            assert "samesite=lax" in deletion
            assert ("secure" in deletion) is cookie_secure
            assert client.cookies.get("planner_view") is None
            assert client.get("/preferences").json()["view"] == "compact"
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def test_cookie_preferences_are_client_local_and_do_not_change_planner(
    api_client, api_service
):
    api_service.add_task("Keep preference isolated", 3)
    data_path = api_service.storage.path
    before_data = data_path.read_bytes()
    before_tasks = api_client.get("/tasks").json()
    before_stats = api_client.get("/stats").json()
    configured_json_path = app.state.settings.json_path
    cookie_selected_path = data_path.with_name("cookie-selected.json")

    default = api_client.get("/preferences")
    assert default.status_code == 200
    assert default.json() == {"view": "compact", "client_version": None}

    with TestClient(app, follow_redirects=False) as second_client:
        second_default = second_client.get("/preferences")
        assert second_default.json() == {
            "view": "compact",
            "client_version": None,
        }

        selected = api_client.put(
            "/preferences",
            json={"view": "detailed"},
            headers={"X-Client-Version": "web-2"},
        )
        assert selected.status_code == 200
        assert selected.json() == {
            "view": "detailed",
            "client_version": "web-2",
        }
        assert selected.headers["X-Planner-Version"] == "1"
        set_cookie = selected.headers["set-cookie"].lower()
        assert "planner_view=detailed" in set_cookie
        assert "path=/preferences" in set_cookie
        assert "httponly" in set_cookie
        assert "samesite=lax" in set_cookie
        assert "secure" not in set_cookie
        assert api_client.cookies.get("planner_view") == "detailed"

        first_read = api_client.get("/preferences")
        assert first_read.json() == {
            "view": "detailed",
            "client_version": None,
        }
        assert first_read.headers["X-Planner-Version"] == "1"

        # Another client has its own jar and cannot see the first client's choice.
        assert second_client.get("/preferences").json() == {
            "view": "compact",
            "client_version": None,
        }
        second_client.cookies.set(
            "planner_view", "admin", path="/preferences"
        )
        unknown_cookie = second_client.get("/preferences")
        assert unknown_cookie.status_code == 200
        assert unknown_cookie.json() == {
            "view": "compact",
            "client_version": None,
        }

        invalid = api_client.put("/preferences", json={"view": "wide"})
        assert invalid.status_code == 422
        assert "set-cookie" not in invalid.headers
        assert api_client.cookies.get("planner_view") == "detailed"
        assert api_client.get("/preferences").json()["view"] == "detailed"

        deleted = api_client.delete("/preferences")
        assert deleted.status_code == 204
        assert deleted.content == b""
        assert deleted.headers["X-Planner-Version"] == "1"
        deletion = deleted.headers["set-cookie"].lower()
        assert "planner_view=" in deletion
        assert "path=/preferences" in deletion
        assert "max-age=0" in deletion
        assert "samesite=lax" in deletion
        assert api_client.cookies.get("planner_view") is None

        after_delete = api_client.get("/preferences")
        assert after_delete.status_code == 200
        assert after_delete.json() == {
            "view": "compact",
            "client_version": None,
        }
        assert after_delete.headers["X-Planner-Version"] == "1"

    api_client.cookies.set(
        "planner_view", str(cookie_selected_path), path="/preferences"
    )
    unknown_cookie = api_client.get("/preferences")
    assert unknown_cookie.status_code == 200
    assert unknown_cookie.json()["view"] == "compact"
    assert app.state.settings.json_path == configured_json_path
    assert not cookie_selected_path.exists()
    api_client.cookies.clear()

    assert data_path.read_bytes() == before_data
    assert api_client.get("/tasks").json() == before_tasks
    assert api_client.get("/stats").json() == before_stats

    commands = iter(("list", "stats", "exit"))
    output = []
    run(api_service, read=lambda _prompt: next(commands), write=output.append)
    rendered = "\n".join(output)
    assert "Keep preference isolated" in rendered
    assert "Всего: 1" in rendered
    assert data_path.read_bytes() == before_data
