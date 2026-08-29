import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@patch("app.api.routes.documents.process_document_task")
def test_upload_document_invalid_type(mock_task):
    # Try uploading a CSV which is unsupported
    files = {"file": ("test.csv", b"dummy content", "text/csv")}
    response = client.post("/api/v1/documents/upload", files=files)
    
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]
    mock_task.delay.assert_not_called()

def test_search_endpoint_no_results():
    # Since DB is empty, it should return gracefully
    with patch("app.api.routes.search.search_chunks") as mock_search:
        mock_search.return_value = []
        response = client.post("/api/v1/search/", json={"query": "test query"})
        
        assert response.status_code == 200
        data = response.json()
        assert "No relevant documents found" in data["answer"]
        assert len(data["sources"]) == 0
