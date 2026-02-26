def test_auth_required_error_shape(client):
    response = client.get("/v1/documents")
    assert response.status_code == 401
    payload = response.json()
    assert "error" in payload
    assert payload["error"]["code"] == "http_error"
    assert payload["error"]["status_code"] == 401
