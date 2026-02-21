from fastapi.testclient import TestClient
from rule_viewer.main import app

client = TestClient(app)


def test_get_single_rule_detail_by_slug():
    slug = "example-rule-slug"
    # Test 200 OK with existing rule slug
    params = {}
    response = client.get(f"/api/rules/{slug}", params=params, timeout=30)
    assert response.status_code == 200
    data = response.json()
    # Basic assertions about returned structure contents
    assert isinstance(data, dict)
    # Must include details and sources - check some key fields expected in RuleDetail
    assert "slug" in data and data["slug"] == slug
    assert "decorator_source" in data
    assert "linter_source" in data

    # Test 404 with a non-existent slug
    non_existent_slug = "nonexistent-rule-slug-xyz123"
    response_404 = client.get(f"/api/rules/{non_existent_slug}", timeout=30)
    assert response_404.status_code == 404
    assert response_404.json().get("detail") == "Rule not found"


test_get_single_rule_detail_by_slug()
