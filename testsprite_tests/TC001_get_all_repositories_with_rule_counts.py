from fastapi import status
from fastapi.testclient import TestClient

from unittest.mock import patch
from rule_viewer.main import app

client = TestClient(app)

def test_get_all_repositories_with_rule_counts(monkeypatch):
    # Patch external service calls to prevent real API calls
    monkeypatch.setattr("rule_viewer.api.routes.check_bedrock_connection", lambda: True)
    monkeypatch.setattr("rule_viewer.api.routes.check_datadog_connection", lambda: True)
    monkeypatch.setattr("rule_viewer.api.routes.check_github_connection", lambda: True)

    # 1) Normal behavior: Return 200 with list of repositories including metadata and rule counts.
    # 2) No repositories tracked: Return 200 with empty list.
    # 3) Server internal error: Return 500.

    url = "/api/repos"

    import rule_viewer.api.routes as routes

    # Sample repo data for normal case
    sample_repos = [
        {
            "id": 1,
            "name": "repo1",
            "full_name": "org/repo1",
            "url": "https://github.com/org/repo1",
            "description": "Test repo 1",
            "rule_count": 5,
            "last_processed": "2026-01-01T12:00:00Z"
        },
        {
            "id": 2,
            "name": "repo2",
            "full_name": "org/repo2",
            "url": "https://github.com/org/repo2",
            "description": "Test repo 2",
            "rule_count": 0,
            "last_processed": None
        }
    ]

    # Patch get_all_repositories to return sample_repos
    monkeypatch.setattr(routes, "get_all_repositories", lambda: sample_repos)
    response = client.get(url, timeout=30)
    assert response.status_code == status.HTTP_200_OK
    repos = response.json()
    assert isinstance(repos, list)
    assert len(repos) == 2
    for repo in repos:
        # Validate keys and types
        assert "id" in repo and isinstance(repo["id"], int)
        assert "name" in repo and isinstance(repo["name"], str)
        assert "full_name" in repo and isinstance(repo["full_name"], str)
        assert "url" in repo and isinstance(repo["url"], str)
        assert "description" in repo and (repo["description"] is None or isinstance(repo["description"], str))
        assert "rule_count" in repo and isinstance(repo["rule_count"], int)
        assert "last_processed" in repo and (repo["last_processed"] is None or isinstance(repo["last_processed"], str))

    # Patch get_all_repositories to return empty list (no repos tracked)
    monkeypatch.setattr(routes, "get_all_repositories", lambda: [])
    response = client.get(url, timeout=30)
    assert response.status_code == status.HTTP_200_OK
    repos = response.json()
    assert isinstance(repos, list)
    assert len(repos) == 0

    # Patch get_all_repositories to raise Exception to simulate internal server error
    def raise_exc():
        raise Exception("Internal error simulation")
    monkeypatch.setattr(routes, "get_all_repositories", raise_exc)

    response = client.get(url, timeout=30)
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

test_get_all_repositories_with_rule_counts()