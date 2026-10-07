def test_one_task_workflow_keeps_control_task_and_state_consistent(api_client):
    health = api_client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    control_response = api_client.post(
        "/tasks", json={"title": "Control", "priority": 1}
    )
    target_response = api_client.post(
        "/tasks", json={"title": "  Review API  ", "priority": 3}
    )
    assert control_response.status_code == 201
    assert target_response.status_code == 201

    control = control_response.json()
    target = target_response.json()
    control_id = control["id"]
    task_id = target["id"]
    path = f"/tasks/{task_id}"
    assert set(target) == {"id", "title", "priority", "is_done"}
    assert target["title"] == "Review API"
    assert target["is_done"] is False
    assert api_client.get(path).json() == target
    assert api_client.get(f"/tasks/{control_id}").json() == control
    assert api_client.get("/tasks").json() == [control, target]
    assert api_client.get("/stats").json() == {
        "total": 2,
        "open": 2,
        "done": 0,
    }

    put_response = api_client.put(
        path,
        json={"title": "Reviewed", "priority": 5, "is_done": True},
    )
    target_done = {
        "id": task_id,
        "title": "Reviewed",
        "priority": 5,
        "is_done": True,
    }
    assert put_response.status_code == 200
    assert put_response.json() == target_done
    assert api_client.get(path).json() == target_done
    assert api_client.get(f"/tasks/{control_id}").json() == control
    assert api_client.get("/stats").json() == {
        "total": 2,
        "open": 1,
        "done": 1,
    }

    before_tasks = api_client.get("/tasks").json()
    before_stats = api_client.get("/stats").json()
    invalid_patch = api_client.patch(path, json={"title": "   "})
    assert invalid_patch.status_code == 422
    assert api_client.get("/tasks").json() == before_tasks
    assert api_client.get("/stats").json() == before_stats

    incomplete_put = api_client.put(path, json={"title": "Incomplete"})
    assert incomplete_put.status_code == 422
    assert api_client.get("/tasks").json() == before_tasks
    assert api_client.get("/stats").json() == before_stats

    patch_response = api_client.patch(path, json={"is_done": False})
    target_open = {
        "id": task_id,
        "title": "Reviewed",
        "priority": 5,
        "is_done": False,
    }
    assert patch_response.status_code == 200
    assert patch_response.json() == target_open
    assert api_client.get(path).json() == target_open
    assert api_client.get(f"/tasks/{control_id}").json() == control
    assert api_client.get("/tasks", params={"is_done": False}).json() == [
        control,
        target_open,
    ]
    assert api_client.get("/stats").json() == {
        "total": 2,
        "open": 2,
        "done": 0,
    }

    empty_patch = api_client.patch(path, json={})
    null_patch = api_client.patch(path, json={"title": None})
    assert empty_patch.status_code == 200
    assert empty_patch.json() == target_open
    assert null_patch.status_code == 200
    assert null_patch.json() == target_open

    deleted = api_client.delete(path)
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert api_client.get(path).status_code == 404
    assert api_client.delete(path).status_code == 404
    assert api_client.put(
        path, json={"title": "Again", "priority": 2, "is_done": False}
    ).status_code == 404
    assert api_client.patch(path, json={"is_done": True}).status_code == 404
    assert api_client.get(f"/tasks/{control_id}").json() == control
    assert api_client.get("/tasks").json() == [control]
    assert api_client.get("/stats").json() == {
        "total": 1,
        "open": 1,
        "done": 0,
    }
