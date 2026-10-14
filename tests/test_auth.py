from database import db_cursor
from tests.conftest import login, register


def test_user_can_register_and_login(client, csrf):
    response = register(client, csrf)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    response = login(client, csrf)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")

    with client.session_transaction() as session:
        assert session["usuario_id"]
        assert session["usuario_nome"] == "Test User"


def test_wrong_password_does_not_create_session(client, csrf):
    register(client, csrf)

    response = login(client, csrf, password="WrongPass123")
    assert response.status_code == 302

    with client.session_transaction() as session:
        assert "usuario_id" not in session

    with db_cursor() as cursor:
        cursor.execute(
            "SELECT tentativas FROM login_attempts WHERE email=%s",
            ("user@example.com",),
        )
        attempt = cursor.fetchone()
    assert attempt["tentativas"] == 1


def test_disabled_registration_redirects_to_login(app, client, csrf):
    app.config["ALLOW_REGISTRATION"] = False

    response = client.post(
        "/register",
        data={
            "csrf_token": csrf,
            "name": "Blocked User",
            "email": "blocked@example.com",
            "password": "StrongPass123",
            "password_confirm": "StrongPass123",
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_inactive_account_email_cannot_be_registered_again():
    from app import services

    user_id = services.criar_usuario("Inactive", "inactive@example.com", "StrongPass123")
    with db_cursor(commit=True) as cursor:
        cursor.execute("UPDATE usuarios SET ativo=0 WHERE id=%s", (user_id,))

    try:
        services.criar_usuario("Duplicate", "inactive@example.com", "StrongPass123")
    except ValueError as error:
        assert "já está cadastrado" in str(error)
    else:
        raise AssertionError("Duplicate inactive e-mail should be rejected.")
