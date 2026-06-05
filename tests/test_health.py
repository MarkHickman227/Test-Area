from fastapi.testclient import TestClient


def test_health_reports_database_status(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] in {"healthy", "degraded"}
    assert "linkedin_configured" in response.json()
