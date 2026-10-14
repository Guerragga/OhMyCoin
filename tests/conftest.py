import os
from pathlib import Path

import pytest

os.environ["APP_ENV"] = "test"
os.environ["TESTING"] = "True"
os.environ["FLASK_DEBUG"] = "False"
os.environ["SECRET_KEY"] = "test-secret-key-with-at-least-thirty-two-characters"
os.environ["SESSION_COOKIE_SECURE"] = "False"
os.environ["DB_HOST"] = os.getenv("DB_HOST", "127.0.0.1")
os.environ["DB_PORT"] = os.getenv("DB_PORT", "3306")
os.environ["DB_USER"] = os.getenv("DB_USER", "ohmycoin_test")
os.environ["DB_PASSWORD"] = os.getenv("DB_PASSWORD", "test_password")
os.environ["DB_NAME"] = os.getenv("DB_NAME", "ohmycoin_test")

from app import create_app
from database import get_connection

TABLES = [
    "audit_logs",
    "login_attempts",
    "pagamentos_dividas",
    "movimentacoes",
    "compras_cartao",
    "dividas",
    "previsoes_mensais",
    "caixinhas",
    "cartoes_credito",
    "contas",
    "categorias",
    "usuarios",
]


def initialize_schema():
    if not os.environ["DB_NAME"].endswith("_test"):
        raise RuntimeError("Tests require a disposable database with a name ending in _test.")
    schema = Path("app/sql/schema.sql").read_text(encoding="utf-8")
    statements = [statement.strip() for statement in schema.split(";") if statement.strip()]
    connection = get_connection()
    cursor = connection.cursor()
    try:
        for statement in statements:
            cursor.execute(statement)
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def reset_database():
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        for table in TABLES:
            cursor.execute(f"TRUNCATE TABLE {table}")
        cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        connection.commit()
    finally:
        cursor.close()
        connection.close()


@pytest.fixture(scope="session", autouse=True)
def schema():
    initialize_schema()


@pytest.fixture(autouse=True)
def clean_database(schema):
    reset_database()


@pytest.fixture()
def app():
    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def csrf(client):
    token = "test-csrf-token"
    with client.session_transaction() as session:
        session["csrf_token"] = token
    return token


def register(client, csrf_token, email="user@example.com", password="StrongPass123"):
    return client.post(
        "/register",
        data={
            "csrf_token": csrf_token,
            "name": "Test User",
            "email": email,
            "password": password,
            "password_confirm": password,
        },
        follow_redirects=False,
    )


def login(client, csrf_token, email="user@example.com", password="StrongPass123"):
    return client.post(
        "/login",
        data={
            "csrf_token": csrf_token,
            "email": email,
            "password": password,
        },
        follow_redirects=False,
    )


@pytest.fixture()
def authenticated_client(client, csrf):
    register(client, csrf)
    login(client, csrf)
    return client
