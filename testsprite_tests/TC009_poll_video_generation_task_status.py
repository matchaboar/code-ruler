from fastapi.testclient import TestClient
from rule_viewer.main import app

# Define the different video responses to test
video_responses = [
    {"task_id": "dummy_task_1", "status": "processing"},
    {"task_id": "dummy_task_2", "status": "completed", "video_url": "http://example.com/video.mp4"},
    {"task_id": "dummy_task_3", "status": "failed", "error": "Generation error"},
]

def test_poll_video_generation_task_status():
    client = TestClient(app)

    repo_id = 1
    rules_response = client.get("/api/rules", params={"repo_id": repo_id}, timeout=30)
    assert rules_response.status_code == 200
    rules = rules_response.json()
    assert isinstance(rules, list)
    assert len(rules) > 0, "No rules available to create video generation task"

    slug = rules[0]["slug"]

    # Submit a video generation request
    video_req_payload = {"prompt": "Test video generation for polling"}
    video_submit_resp = client.post(f"/api/rules/{slug}/generate-video", json=video_req_payload, timeout=30)
    assert video_submit_resp.status_code == 200
    video_submit_data = video_submit_resp.json()
    assert "task_id" in video_submit_data

    task_id = video_submit_data["task_id"]

    from fastapi.responses import JSONResponse

    # Patch the endpoint to return the moment video_response
    for video_response in video_responses:
        target_route = None
        for r in app.routes:
            if getattr(r, "path", None) == "/api/video/{task_id}" and "GET" in r.methods:
                target_route = r
                break

        assert target_route is not None

        original_endpoint = target_route.endpoint

        async def mock_endpoint(task_id_param: str):
            resp_data = dict(video_response)
            resp_data["task_id"] = task_id_param
            return JSONResponse(status_code=200, content=resp_data)

        try:
            target_route.endpoint = mock_endpoint
            resp = client.get(f"/api/video/{task_id}", timeout=30)
            assert resp.status_code == 200

            data = resp.json()
            assert data["task_id"] == task_id

            status_value = data.get("status")
            assert status_value in ("processing", "completed", "failed")

            if status_value == "processing":
                assert "video_url" not in data
                assert "error" not in data
            elif status_value == "completed":
                assert "video_url" in data
                assert isinstance(data["video_url"], str)
            elif status_value == "failed":
                assert "error" in data
                assert isinstance(data["error"], str)
        finally:
            target_route.endpoint = original_endpoint


test_poll_video_generation_task_status()