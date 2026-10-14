from app.services.common import validar_senha


def test_health_endpoints(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}

    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ready"}


def test_csrf_blocks_unsafe_request_without_token(client):
    response = client.post(
        "/register",
        data={
            "name": "No Token",
            "email": "no-token@example.com",
            "password": "StrongPass123",
            "password_confirm": "StrongPass123",
        },
    )
    assert response.status_code == 400


def test_security_headers_are_present(client):
    response = client.get("/login")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in response.headers
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_password_policy_rejects_weak_password():
    try:
        validar_senha("onlyletters")
    except ValueError as error:
        assert "letras e números" in str(error)
    else:
        raise AssertionError("Weak password should have been rejected.")
