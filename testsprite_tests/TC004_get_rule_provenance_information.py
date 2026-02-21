import pytest
from fastapi.testclient import TestClient
from rule_viewer.main import app
from tests.conftest import db_session  # Assuming db_session fixture is available for DB operations


@pytest.mark.usefixtures("db_session")
def test_get_rule_provenance_information(db_session):
    """
    Test the GET /api/rules/{slug}/provenance endpoint:
    - Verify 200 and correct provenance data for existing rule
    - Verify 404 for nonexistent rule
    """
    client = TestClient(app)

    # Utility function to create a rule with provenance info
    # Should use actual ORM models and session or any available fixture to add rule and provenance data
    from code_ruler.db import models

    rule_slug = "test-rule-slug-provenance"

    # Create a rule with provenance data for test
    rule = models.Rule(
        slug=rule_slug,
        name="Test Rule for Provenance",
        repo_id=1,
        is_active=True,
        category="best_practice",
        severity="medium",
        description="A test rule to check provenance",
    )

    # Add provenance items related to the rule
    provenance_item = models.Provenance(
        rule=rule,
        pr_number=42,
        pr_title="Fix test rule issue",
        pr_url="https://github.com/org/repo/pull/42",
        author="testauthor",
        diff_hunks=["@@ -1,4 +1,4 @@\n-test\n+test"],
        file_paths=["src/code/test_file.py"],
    )

    # Add rule and provenance item to db session
    db_session.add(rule)
    db_session.add(provenance_item)
    db_session.commit()

    try:
        # Test existing rule provenance retrieval
        response = client.get(f"/api/rules/{rule_slug}/provenance", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(
            item.get("pr_number") == 42 and
            item.get("author") == "testauthor" and
            "diff_hunks" in item and
            "file_paths" in item
            for item in data
        )

        # Test nonexistent rule provenance returns 404
        nonexistent_slug = "nonexistent-rule-slug-provenance"
        response_404 = client.get(f"/api/rules/{nonexistent_slug}/provenance", timeout=30)
        assert response_404.status_code == 404
        assert response_404.json().get("detail") == "Rule not found"
    finally:
        # Cleanup: remove added provenance and rule
        db_session.delete(provenance_item)
        db_session.delete(rule)
        db_session.commit()


test_get_rule_provenance_information()