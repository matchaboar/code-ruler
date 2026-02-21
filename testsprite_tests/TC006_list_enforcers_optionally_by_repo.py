import pytest
from fastapi.testclient import TestClient
from rule_viewer.main import app

client = TestClient(app)


@pytest.fixture
def create_repo(test_db):
    from code_ruler.db.models import Repo
    repo = Repo(name="test-repo", full_name="org/test-repo")
    test_db.add(repo)
    test_db.commit()
    test_db.refresh(repo)
    yield repo
    test_db.delete(repo)
    test_db.commit()


@pytest.fixture
def create_rule(test_db, create_repo):
    from code_ruler.db.models import Rule
    rule = Rule(
        slug="test-rule",
        repo_id=create_repo.id,
        category="style",
        severity="medium",
        is_active=True,
        negative_example="some negative example",
    )
    test_db.add(rule)
    test_db.commit()
    test_db.refresh(rule)
    yield rule
    test_db.delete(rule)
    test_db.commit()


@pytest.fixture
def generate_enforcer(test_db, create_rule):
    from code_ruler.db.models import Enforcer
    enforcer = Enforcer(
        rule_slug=create_rule.slug,
        repo_id=create_rule.repo_id,
        source="print('enforcer script')",
    )
    test_db.add(enforcer)
    test_db.commit()
    test_db.refresh(enforcer)
    yield enforcer
    test_db.delete(enforcer)
    test_db.commit()


def test_list_enforcers_optionally_by_repo(create_repo, create_rule, generate_enforcer):
    # Test without repo_id filter - should list all enforcers
    response = client.get("/api/enforcers", timeout=30)
    assert response.status_code == 200
    enforcers = response.json()
    assert isinstance(enforcers, list)
    assert any(enf["rule_slug"] == create_rule.slug for enf in enforcers)

    # Test with repo_id filter - should list only enforcers for that repo
    response_filtered = client.get(f"/api/enforcers?repo_id={create_repo.id}", timeout=30)
    assert response_filtered.status_code == 200
    filtered_enforcers = response_filtered.json()
    assert isinstance(filtered_enforcers, list)
    assert all(enf["repo_id"] == create_repo.id for enf in filtered_enforcers)
    # Should include the enforcer created linked to this repo
    assert any(enf["rule_slug"] == create_rule.slug for enf in filtered_enforcers)
    # Test with a repo_id that doesn't exist, result should be empty list (assuming)
    response_empty = client.get("/api/enforcers?repo_id=999999", timeout=30)
    assert response_empty.status_code == 200
    assert response_empty.json() == []


# Note: The test invocation is omitted since environment likely manages test execution
