import pytest
from fastapi.testclient import TestClient
from rule_viewer.main import app

client = TestClient(app, timeout=30)


@pytest.fixture
def create_repo_and_rules(db_session):
    from code_ruler.db.models import Repository, Rule

    # Create a repo
    repo = Repository(name="TestRepo", full_name="org/TestRepo")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    # Create rules with various attributes for filtering
    rules_to_add = [
        Rule(
            repo_id=repo.id,
            slug="rule-1",
            category="best_practice",
            severity="medium",
            is_active=True,
            name="Rule One",
            description="Test rule one",
        ),
        Rule(
            repo_id=repo.id,
            slug="rule-2",
            category="style",
            severity="high",
            is_active=False,
            name="Rule Two",
            description="Test rule two",
        ),
        Rule(
            repo_id=repo.id,
            slug="rule-3",
            category="best_practice",
            severity="low",
            is_active=True,
            name="Variable naming",
            description="Test rule three",
        ),
        Rule(
            repo_id=repo.id,
            slug="rule-4",
            category="security",
            severity="medium",
            is_active=True,
            name="Security rule",
            description="Test rule four",
        ),
    ]
    db_session.add_all(rules_to_add)
    db_session.commit()
    yield repo
    # Cleanup
    for rule in rules_to_add:
        db_session.delete(rule)
    db_session.delete(repo)
    db_session.commit()


def test_get_rules_with_filters_and_search(create_repo_and_rules):
    repo = create_repo_and_rules
    base_url = "/api/rules"
    repo_id = repo.id

    # 1) Valid call with only repo_id required
    response = client.get(base_url, params={"repo_id": repo_id})
    assert response.status_code == 200
    resp_json = response.json()
    assert isinstance(resp_json, list)
    assert all("slug" in r for r in resp_json)
    assert all(r["repo_id"] == repo_id for r in resp_json)

    # 2) Filter by category=best_practice
    response = client.get(base_url, params={"repo_id": repo_id, "category": "best_practice"})
    assert response.status_code == 200
    results = response.json()
    assert all(r["category"] == "best_practice" for r in results)

    # 3) Filter by severity=medium
    response = client.get(base_url, params={"repo_id": repo_id, "severity": "medium"})
    assert response.status_code == 200
    results = response.json()
    assert all(r["severity"] == "medium" for r in results)

    # 4) Filter by is_active=true
    response = client.get(base_url, params={"repo_id": repo_id, "is_active": "true"})
    assert response.status_code == 200
    results = response.json()
    assert all(r["is_active"] is True for r in results)

    # 5) Filter by is_active=false
    response = client.get(base_url, params={"repo_id": repo_id, "is_active": "false"})
    assert response.status_code == 200
    results = response.json()
    assert all(r["is_active"] is False for r in results)

    # 6) Search with 'variable' string (case insensitive)
    response = client.get(base_url, params={"repo_id": repo_id, "search": "variable"})
    assert response.status_code == 200
    results = response.json()
    # Ensure each result's name or description contains 'variable' case-insensitive
    assert all(
        ("variable" in (r.get("name") or "").lower()) or ("variable" in (r.get("description") or "").lower())
        for r in results
    )

    # 7) Combined filters category=best_practice, severity=medium, is_active=true, search='rule'
    response = client.get(
        base_url,
        params={
            "repo_id": repo_id,
            "category": "best_practice",
            "severity": "medium",
            "is_active": "true",
            "search": "rule",
        },
    )
    assert response.status_code == 200
    results = response.json()
    for r in results:
        assert r["category"] == "best_practice"
        assert r["severity"] == "medium"
        assert r["is_active"] is True
        combined_text = (r.get("name") or "") + " " + (r.get("description") or "")
        assert "rule" in combined_text.lower()

    # 8) Missing required repo_id param -> expect 400
    response = client.get(base_url)
    assert response.status_code == 400
    err = response.json()
    assert "detail" in err
