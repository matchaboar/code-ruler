from fastapi.testclient import TestClient
from unittest.mock import patch
from rule_viewer.main import app

client = TestClient(app)

def test_credentials_status_all_success():
    with patch("rule_viewer.api.routes.check_aws_bedrock_connection", return_value=True), \
         patch("rule_viewer.api.routes.check_datadog_connection", return_value=True), \
         patch("rule_viewer.api.routes.check_github_connection", return_value=True):
        response = client.get("/api/credentials/status", timeout=30)
    assert response.status_code == 200
    json_resp = response.json()
    assert "bedrock" in json_resp and json_resp["bedrock"] is True
    assert "datadog" in json_resp and json_resp["datadog"] is True
    assert "github" in json_resp and json_resp["github"] is True

def test_credentials_status_partial_failure():
    with patch("rule_viewer.api.routes.check_aws_bedrock_connection", return_value=False), \
         patch("rule_viewer.api.routes.check_datadog_connection", return_value=True), \
         patch("rule_viewer.api.routes.check_github_connection", return_value=False):
        response = client.get("/api/credentials/status", timeout=30)
    assert response.status_code == 200
    json_resp = response.json()
    assert "bedrock" in json_resp and json_resp["bedrock"] is False
    assert "datadog" in json_resp and json_resp["datadog"] is True
    assert "github" in json_resp and json_resp["github"] is False

def test_credentials_status_subsystem_error():
    def raise_exception():
        raise Exception("Subsystem failure")

    with patch("rule_viewer.api.routes.check_aws_bedrock_connection", side_effect=raise_exception), \
         patch("rule_viewer.api.routes.check_datadog_connection", side_effect=raise_exception), \
         patch("rule_viewer.api.routes.check_github_connection", side_effect=raise_exception):
        response = client.get("/api/credentials/status", timeout=30)
    assert response.status_code == 500
    json_resp = response.json()
    assert "detail" in json_resp and isinstance(json_resp["detail"], str)

if __name__ == "__main__":
    test_credentials_status_all_success()
    test_credentials_status_partial_failure()
    test_credentials_status_subsystem_error()