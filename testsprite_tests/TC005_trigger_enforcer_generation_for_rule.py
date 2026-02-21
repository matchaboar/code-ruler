import pytest
from fastapi.testclient import TestClient
from rule_viewer.main import app
from code_ruler.db import models
from sqlalchemy.orm import Session
from tests.utils import create_rule_in_db, delete_rule_from_db

client = TestClient(app)

@pytest.fixture
def rule_with_negative_example(db: Session) -> models.Rule:
    rule = create_rule_in_db(db, negative_example="some negative example")
    yield rule
    delete_rule_from_db(db, rule.slug)

@pytest.fixture
def rule_without_negative_example(db: Session) -> models.Rule:
    rule = create_rule_in_db(db, negative_example=None)
    yield rule
    delete_rule_from_db(db, rule.slug)

@pytest.fixture
def slug_enforcer_in_progress(db: Session, rule_with_negative_example: models.Rule) -> str:
    # Mark generation_in_progress in db for this rule
    rule = rule_with_negative_example
    rule.enforcer_generation_in_progress = True
    db.commit()
    yield rule.slug
    # Reset flag after test
    rule.enforcer_generation_in_progress = False
    db.commit()

def test_post_generate_enforcer_success(rule_with_negative_example):
    slug = rule_with_negative_example.slug
    response = client.post(f"/api/rules/{slug}/generate-enforcer", timeout=30)
    assert response.status_code == 200
    json_data = response.json()
    assert "job_id" in json_data
    assert isinstance(json_data["job_id"], str)

def test_post_generate_enforcer_400_no_negative_example(rule_without_negative_example):
    slug = rule_without_negative_example.slug
    response = client.post(f"/api/rules/{slug}/generate-enforcer", timeout=30)
    assert response.status_code == 400
    json_data = response.json()
    # Assuming error detail returned in a "detail" field
    assert "negative_example" in json_data.get("detail", "").lower()

def test_post_generate_enforcer_409_generation_in_progress(slug_enforcer_in_progress):
    slug = slug_enforcer_in_progress
    response = client.post(f"/api/rules/{slug}/generate-enforcer", timeout=30)
    assert response.status_code == 409
    json_data = response.json()
    assert "already in progress" in json_data.get("detail", "").lower()

def test_post_generate_enforcer_404_rule_not_found():
    slug = "nonexistent-rule-slug"
    response = client.post(f"/api/rules/{slug}/generate-enforcer", timeout=30)
    assert response.status_code == 404
    json_data = response.json()
    assert "not found" in json_data.get("detail", "").lower()

test_post_generate_enforcer_success()
test_post_generate_enforcer_400_no_negative_example()
test_post_generate_enforcer_409_generation_in_progress()
test_post_generate_enforcer_404_rule_not_found()