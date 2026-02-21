from fastapi.testclient import TestClient
from rule_viewer.main import app
from code_ruler.db import models
from sqlalchemy.orm import Session
from unittest.mock import patch

client = TestClient(app)

def create_rule(db: Session):
    # Create a sample repo and rule to use in tests
    repo = models.Repo(name="test-repo", full_name="org/test-repo")
    db.add(repo)
    db.commit()
    db.refresh(repo)

    rule = models.Rule(
        slug="test-rule",
        repo_id=repo.id,
        title="Test Rule",
        category="best_practice",
        severity="medium",
        is_active=True,
        description="Desc",
        negative_example="some negative example",
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    return rule.slug

# Assuming we have a way to get a DB session here. For example purposes, you might adjust this for your environment.
from code_ruler.db.session import SessionLocal

def test_post_generate_video():
    db = SessionLocal()
    slug = create_rule(db)

    url = f"/api/rules/{slug}/generate-video"

    # Patch the external minimax call to not do real API calls
    with patch("code_ruler.video.minimax_client.MinimaxClient.submit_video_generation") as mock_submit:
        mock_submit.return_value = "fake-task-id-123"

        # Test successful request with prompt
        response = client.post(url, json={"prompt": "Show how the rule transforms code"})
        assert response.status_code == 200
        json_data = response.json()
        assert "task_id" in json_data
        assert json_data["task_id"] == "fake-task-id-123"

        # Test successful request without prompt (optional)
        response2 = client.post(url, json={})
        assert response2.status_code == 200
        json_data2 = response2.json()
        assert "task_id" in json_data2
        assert json_data2["task_id"] == "fake-task-id-123"

    # Test 404 Not Found for non-existent rule slug
    response_404 = client.post("/api/rules/nonexistent-slug/generate-video", json={"prompt": "test"})
    assert response_404.status_code == 404
    resp_json = response_404.json()
    assert "detail" in resp_json

    # Cleanup
    # Delete the created rule and repo
    from sqlalchemy.orm import Session
    rule_obj = db.query(models.Rule).filter(models.Rule.slug == slug).first()
    if rule_obj:
        db.delete(rule_obj)
    repo_obj = db.query(models.Repo).filter(models.Repo.id == rule_obj.repo_id).first() if rule_obj else None
    if repo_obj:
        db.delete(repo_obj)
    db.commit()
    db.close()

test_post_generate_video()
