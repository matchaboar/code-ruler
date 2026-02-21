from fastapi.testclient import TestClient
from rule_viewer.main import app
from sqlmodel import Session, select
from code_ruler.db import models

client = TestClient(app)

def test_get_enforcer_detail_for_rule(client: TestClient = client, db_session: Session = None):
    slug = None
    # Query for a rule that has an enforcer (assuming enforcer relation exists)
    if db_session:
        statement = select(models.Rule).where(
            models.Rule.slug.in_(
                select(models.Enforcer.rule_slug)
            )
        ).limit(1)
        rule_with_enforcer = db_session.exec(statement).first()
    else:
        rule_with_enforcer = None

    if rule_with_enforcer:
        slug = rule_with_enforcer.slug

    # If no existing rule with enforcer found, create one
    if not slug and db_session:
        # Create a test rule
        test_rule = models.Rule(
            slug="test-rule-slug-for-enforcer",
            name="Test Rule",
            repo_id=1,
            category="best_practice",
            severity="medium",
            is_active=True,
            negative_example="some negative example"
        )
        db_session.add(test_rule)
        db_session.commit()
        db_session.refresh(test_rule)
        slug = test_rule.slug

        # Create a related enforcer for this rule
        test_enforcer = models.Enforcer(
            rule_slug=slug,
            source="def lint_check(): pass",
            tests='[{"test_case": "example"}]',
            traces='[]'
        )
        db_session.add(test_enforcer)
        db_session.commit()

        try:
            # GET existing enforcer detail - expect 200
            response = client.get(f"/api/rules/{slug}/enforcer", timeout=30.0)
            assert response.status_code == 200
            data = response.json()
            assert "source" in data
            assert "tests" in data
            assert "traces" in data

            # Test 404 for non-existent rule/enforcer
            bad_slug = "nonexistent-enforcer-rule"
            resp_404 = client.get(f"/api/rules/{bad_slug}/enforcer", timeout=30.0)
            assert resp_404.status_code == 404
        finally:
            # Cleanup created enforcer and rule
            db_session.delete(test_enforcer)
            db_session.delete(test_rule)
            db_session.commit()
    elif slug:
        # If we found an existing slug with enforcer, test the endpoint directly
        response = client.get(f"/api/rules/{slug}/enforcer", timeout=30.0)
        assert response.status_code == 200
        data = response.json()
        assert "source" in data
        assert "tests" in data
        assert "traces" in data

        # Test 404 for a non-existent slug
        bad_slug = "nonexistent-enforcer-rule"
        resp_404 = client.get(f"/api/rules/{bad_slug}/enforcer", timeout=30.0)
        assert resp_404.status_code == 404


test_get_enforcer_detail_for_rule()
