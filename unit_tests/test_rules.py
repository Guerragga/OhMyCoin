from datetime import date
from decimal import Decimal

import pytest

from app import create_app
from app.services.cards import _mes_vencimento_primeira_parcela
from app.services.common import decimal_brl, normalizar_mes, validar_url_imagem
from app.services.debts import _paid_numbers


@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity", "1e100", "-1", "0", "abc"])
def test_invalid_money(value):
    with pytest.raises(ValueError):
        decimal_brl(value)


def test_money_keeps_decimal_cents():
    assert decimal_brl("R$ 1.234,56") == Decimal("1234.56")


@pytest.mark.parametrize("month", ["2026-00", "2026-13", "2026-1", "2026-01extra", "9999-12", "0001-01"])
def test_invalid_month(month):
    with pytest.raises(ValueError):
        normalizar_mes(month)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/a.png",
        "https://localhost/a",
        "https://127.0.0.1/",
        "https://[::1]/",
        "https://10.0.0.1/",
        "https://169.254.169.254/",
        "https://192.168.1.1/",
        "https://localhost./",
        "https://host.internal/",
        "https://2130706433/",
        "https://127.1/",
        "https://example.com:bad/",
        "https://user:pass@example.com/",
        "https://[invalid/",
    ],
)
def test_local_or_malformed_image_url(url):
    with pytest.raises(ValueError):
        validar_url_imagem(url)


def test_external_image_url():
    assert validar_url_imagem("https://example.com/logo.png") == "https://example.com/logo.png"


@pytest.mark.parametrize(
    "purchase,closing,due,expected",
    [
        ("2026-01-10", 10, 18, "2026-01"),
        ("2026-01-11", 10, 18, "2026-02"),
        ("2026-12-31", 10, 5, "2027-02"),
        ("2026-02-28", 31, 5, "2026-03"),
        ("2028-02-29", 31, 5, "2028-03"),
    ],
)
def test_invoice_boundaries(purchase, closing, due, expected):
    assert (
        _mes_vencimento_primeira_parcela(
            date.fromisoformat(purchase),
            {
                "dia_fechamento": closing,
                "dia_vencimento": due,
            },
        )
        == expected
    )


def test_out_of_order_payments_do_not_mark_first_installment_paid():
    assert _paid_numbers({"parcelas_pagas": 1}, [{"parcela_numero": 3}]) == {3}
    assert _paid_numbers({"parcelas_pagas": 3}, [{"parcela_numero": 5}]) == {1, 2, 5}


def test_public_login_and_security_headers():
    app = create_app()
    response = app.test_client().get("/login")
    assert response.status_code == 200
    assert "upgrade-insecure-requests" not in response.headers["Content-Security-Policy"]
    assert b'name="csrf_token"' in response.data


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_csrf_all_unsafe_methods(method):
    client = create_app().test_client()
    assert getattr(client, method)("/register").status_code == 400


def test_csrf_markup_escapes_session_value():
    client = create_app().test_client()
    with client.session_transaction() as session:
        session["csrf_token"] = '"><script>alert(1)</script>'
    response = client.get("/login")
    assert b"<script>alert(1)</script>" not in response.data
    assert b"&lt;script&gt;" in response.data


def test_non_ascii_csrf_token_is_rejected_without_server_error():
    client = create_app().test_client()
    client.get("/login")
    assert client.post("/register", data={"csrf_token": "inválido"}).status_code == 400


@pytest.mark.parametrize("path", ["/dashboard", "/cartoes", "/previsoes", "/dividas", "/movimentacoes"])
def test_invalid_month_is_bad_request(path):
    assert create_app().test_client().get(path + "?mes=not-a-month").status_code == 400


def test_readiness_reports_unavailable(monkeypatch):
    monkeypatch.setattr("app.database_ready", lambda: False)
    response = create_app().test_client().get("/readyz")
    assert response.status_code == 503


def test_production_rejects_demo_secret_and_debug(monkeypatch):
    from config import Config

    monkeypatch.setattr(Config, "IS_PRODUCTION", True)
    monkeypatch.setattr(Config, "SECRET_KEY", "generate-a-random-value-before-running")
    monkeypatch.setattr(Config, "DEBUG", False)
    monkeypatch.setattr(Config, "TESTING", False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Config.validate_security()
    monkeypatch.setattr(Config, "DEBUG", True)
    with pytest.raises(RuntimeError, match="DEBUG"):
        Config.validate_security()
