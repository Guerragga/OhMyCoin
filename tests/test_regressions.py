from datetime import date
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import services
from app.services.accounts import saldo_conta
from app.services.cards import compromisso_cartao, meses_a_partir
from app.services.common import somar_meses
from app.services.users import usuario_e_admin
from app.services.dashboard import despesas_por_categoria, total_dividas_mes
from database import db_cursor
from tests.conftest import login, register


def user(email="audit@example.com"):
    return services.criar_usuario("Example User", email, "StrongPass123")


def debt(uid, paid=0, count=4):
    account = services.listar_contas(uid)[0]
    services.salvar_divida(
        uid,
        {
            "descricao": "Example debt",
            "valor_parcela": "100",
            "parcelas_total": str(count),
            "parcelas_pagas": str(paid),
            "data_inicio": date.today().replace(day=1).isoformat(),
            "dia_vencimento": "20",
            "conta_id": str(account["id"]),
            "ativa": "1",
        },
    )
    return services.listar_dividas(uid)[0], account


def card(uid):
    services.salvar_cartao(
        uid,
        {
            "nome": "Example Card",
            "limite_total": "1000",
            "dia_fechamento": "10",
            "dia_vencimento": "18",
        },
    )
    return services.listar_cartoes(uid)[0]


def token(client):
    with client.session_transaction() as session:
        return session["csrf_token"]


def test_out_of_order_debt_payment_and_undo():
    uid = user()
    item, account = debt(uid)
    current = date.today().strftime("%Y-%m")
    third = somar_meses(date.today().replace(day=1), 2).strftime("%Y-%m")
    services.pagar_parcela_divida(uid, item["id"], third)
    assert not services.parcelas_dividas_mes(uid, current)[0]["paga"]
    assert services.parcelas_dividas_mes(uid, third)[0]["paga"]
    assert services.listar_dividas(uid)[0]["parcelas_pagas"] == 1
    assert total_dividas_mes(uid, current) == Decimal("200")  # Paid third + open first.
    assert total_dividas_mes(uid, third) == Decimal("0")
    mov = services.listar_movimentacoes(uid)[0]
    services.deletar_movimentacao(uid, mov["id"])
    assert services.listar_dividas(uid)[0]["parcelas_pagas"] == 0
    assert saldo_conta(uid, account["id"]) == 0
    assert not services.parcelas_dividas_mes(uid, third)[0]["paga"]


def test_debt_repayment_after_undo_reopens_paid_off_debt():
    uid = user()
    item, _ = debt(uid, count=1)
    services.antecipar_proxima_parcela_divida(uid, item["id"])
    assert services.obter_divida(uid, item["id"])["status"] == "quitada"
    services.deletar_movimentacao(uid, services.listar_movimentacoes(uid)[0]["id"])
    assert services.obter_divida(uid, item["id"])["status"] == "ativa"
    services.antecipar_proxima_parcela_divida(uid, item["id"])
    assert len(services.listar_movimentacoes(uid)) == 1


def test_imported_paid_installments_cannot_be_paid_again():
    uid = user()
    item, _ = debt(uid, paid=1)
    with pytest.raises(ValueError, match="já está"):
        services.pagar_parcela_divida(uid, item["id"], date.today().strftime("%Y-%m"))
    assert services.antecipar_proxima_parcela_divida(uid, item["id"]) == 2
    assert services.listar_dividas(uid)[0]["parcelas_pagas"] == 2


def test_debt_payment_cannot_be_edited_as_manual_transaction():
    uid = user()
    item, account = debt(uid)
    services.antecipar_proxima_parcela_divida(uid, item["id"])
    mov = services.listar_movimentacoes(uid)[0]
    with pytest.raises(ValueError, match="Estorne"):
        services.salvar_movimentacao(
            uid, {"tipo": "despesa", "valor": "999", "descricao": "Changed", "conta_id": account["id"]}, mov["id"]
        )
    assert services.obter_movimentacao(uid, mov["id"])["valor"] == 100


def test_concurrent_payment_creates_one_expense():
    uid = user()
    item, _ = debt(uid)

    def pay(_):
        try:
            services.pagar_parcela_divida(uid, item["id"], date.today().strftime("%Y-%m"))
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(pay, range(2))) == [False, True]
    assert len(services.listar_movimentacoes(uid)) == 1
    assert services.obter_divida(uid, item["id"])["parcelas_pagas"] == 1


@pytest.mark.parametrize("amount,count", [("100", 3), ("1", 6), ("0.05", 3), ("99.99", 240)])
def test_installments_are_positive_and_sum_to_purchase(amount, count):
    uid = user()
    item = card(uid)
    services.registrar_compra_cartao(
        uid,
        {
            "cartao_id": item["id"],
            "descricao": "Purchase",
            "valor_total": amount,
            "parcelas": str(count),
            "data_compra": "2026-01-01",
        },
    )
    values = [
        p["valor"]
        for month in meses_a_partir("2026-01", count + 1)
        for p in services.parcelas_cartao_mes(uid, month, item["id"])
    ]
    assert len(values) == count
    assert min(values) > 0
    assert sum(values) == Decimal(amount)


def test_future_installments_commit_credit_limit_and_unified_list_is_not_duplicated():
    uid = user()
    item = card(uid)
    services.salvar_movimentacao(
        uid,
        {
            "tipo": "despesa",
            "valor": "600",
            "descricao": "Purchase",
            "forma_pagamento": "cartao",
            "cartao_id": item["id"],
            "parcelas": "3",
            "data_movimentacao": "2026-01-01",
        },
    )
    assert len(services.listar_movimentacoes(uid)) == 1
    assert compromisso_cartao(uid, "2026-01", item["id"]) == 600
    assert services.listar_cartoes(uid, ano_mes="2026-01")[0]["limite_disponivel_estimado"] == 400
    services.deletar_compra_cartao(uid, services.listar_compras_cartao(uid)[0]["id"])
    assert services.listar_movimentacoes(uid) == []


def test_dashboard_paid_debt_not_counted_twice():
    uid = user()
    item, _ = debt(uid)
    month = date.today().strftime("%Y-%m")
    before = services.obter_resumo_dashboard(uid, month)
    assert before["despesas_reais"] == 0
    assert before["despesas_comprometidas"] == 100
    services.pagar_parcela_divida(uid, item["id"], month)
    after = services.obter_resumo_dashboard(uid, month)
    assert after["despesas_reais"] == 100
    assert after["despesas_comprometidas"] == 100
    assert sum(Decimal(str(c["total"])) for c in despesas_por_categoria(uid, month)) == 100


def test_concurrent_savings_withdrawals_do_not_overdraw():
    uid = user()
    services.salvar_caixinha(uid, {"nome": "Goal", "valor_guardado": "100"})
    item = services.listar_caixinhas(uid)[0]

    def withdraw(_):
        try:
            services.movimentar_caixinha(uid, item["id"], "80", "retirar")
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(withdraw, range(2))) == [False, True]
    assert services.obter_caixinha(uid, item["id"])["valor_guardado"] == 20


def test_demo_seed_authentication_and_idempotence(app, client, csrf):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    demo = services.obter_usuario_por_email("demo@example.com")
    assert services.senha_confere(demo["senha"], "Demo@12345")
    with db_cursor(commit=True) as cursor:
        cursor.execute("UPDATE usuarios SET nome=%s WHERE id=%s", ("Changed demo", demo["id"]))
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    assert services.obter_usuario_por_id(demo["id"])["nome"] == "Changed demo"
    assert login(client, csrf, "demo@example.com", "Demo@12345").headers["Location"].endswith("/dashboard")
    for path in ["/dashboard", "/contas", "/cartoes", "/dividas", "/caixinhas", "/previsoes", "/movimentacoes"]:
        assert client.get(path).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/perfil",
        "/configuracoes",
        "/categorias",
        "/contas",
        "/movimentacoes",
        "/previsoes",
        "/cartoes",
        "/dividas",
        "/caixinhas",
        "/admin",
    ],
)
def test_all_private_pages_require_login(client, path):
    assert client.get(path).headers["Location"].endswith("/login")


def test_admin_and_disabled_session(client, csrf):
    register(client, csrf)
    login(client, csrf)
    assert client.get("/admin").headers["Location"].endswith("/dashboard")
    with client.session_transaction() as session:
        uid = session["usuario_id"]
    with db_cursor(commit=True) as cursor:
        cursor.execute("UPDATE usuarios SET nivel_acesso='ADMIN' WHERE id=%s", (uid,))
    assert client.get("/admin").status_code == 200
    with db_cursor(commit=True) as cursor:
        cursor.execute("UPDATE usuarios SET ativo=0 WHERE id=%s", (uid,))
    assert client.get("/dashboard").headers["Location"].endswith("/login")


def test_password_change_revokes_other_sessions(client, csrf):
    register(client, csrf)
    login(client, csrf)
    uid = services.obter_usuario_por_email("user@example.com")["id"]
    services.alterar_senha_perfil(
        uid, {"senha_atual": "StrongPass123", "nova_senha": "NewStrongPass123", "confirmar_senha": "NewStrongPass123"}
    )
    assert client.get("/dashboard").headers["Location"].endswith("/login")


def test_logout_requires_csrf(authenticated_client):
    client = authenticated_client
    assert client.post("/logout").status_code == 400
    assert client.post("/logout", data={"csrf_token": token(client)}).status_code == 302
    with client.session_transaction() as session:
        assert "usuario_id" not in session


def test_rate_limit_survives_ip_rotation(client, csrf):
    register(client, csrf)
    for _ in range(5):
        login(client, csrf, password="WrongPass123")
    response = client.post(
        "/login",
        data={"csrf_token": csrf, "email": "user@example.com", "password": "StrongPass123"},
        environ_overrides={"REMOTE_ADDR": "203.0.113.20"},
    )
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as session:
        assert "usuario_id" not in session
    with db_cursor() as cursor:
        cursor.execute("SELECT detalhes, ip FROM audit_logs")
        assert all(not row["detalhes"] and not row["ip"] for row in cursor.fetchall())


def test_cross_user_references_and_deletions_are_rejected():
    first, second = user(), user("second@example.com")
    item, account = debt(first)
    credit = card(first)
    category = services.listar_categorias(first)[0]
    services.salvar_caixinha(first, {"nome": "Private", "valor_guardado": "100"})
    goal = services.listar_caixinhas(first)[0]
    actions = [
        lambda: services.obter_cartao(second, credit["id"]),
        lambda: services.obter_divida(second, item["id"]),
        lambda: services.obter_categoria(second, category["id"]),
        lambda: services.movimentar_caixinha(second, goal["id"], "10", "retirar"),
        lambda: services.deletar_conta(second, account["id"]),
        lambda: services.pagar_parcela_divida(second, item["id"], date.today().strftime("%Y-%m")),
        lambda: services.registrar_compra_cartao(
            second, {"cartao_id": credit["id"], "descricao": "Bad", "valor_total": "10"}
        ),
        lambda: services.salvar_movimentacao(
            second, {"tipo": "receita", "valor": "10", "descricao": "Bad", "conta_id": account["id"]}
        ),
    ]
    for action in actions:
        with pytest.raises(ValueError):
            action()
    assert services.obter_caixinha(first, goal["id"])["valor_guardado"] == 100


def test_category_account_forecast_crud_and_duplicate_errors():
    uid = user()
    services.criar_categoria(uid, "Custom", "despesa")
    category = next(c for c in services.listar_categorias(uid) if c["nome"] == "Custom")
    with pytest.raises(ValueError):
        services.criar_categoria(uid, "Custom", "despesa")
    services.atualizar_categoria(uid, category["id"], "Changed", "geral")
    services.salvar_conta(uid, {"nome": "New", "saldo_inicial": "100"})
    account = next(c for c in services.listar_contas(uid) if c["nome"] == "New")
    services.salvar_previsao(
        uid,
        {
            "ano_mes": "2026-09",
            "tipo": "despesa",
            "descricao": "Budget",
            "valor_previsto": "50",
            "categoria_id": category["id"],
            "conta_id": account["id"],
        },
    )
    forecast = services.listar_previsoes(uid, "2026-09")[0]
    services.deletar_categoria(uid, category["id"])
    services.deletar_conta(uid, account["id"])
    assert services.obter_previsao(uid, forecast["id"])["categoria_id"] is None
    assert services.obter_previsao(uid, forecast["id"])["conta_id"] is None
    services.deletar_previsao(uid, forecast["id"])
    assert services.listar_previsoes(uid, "2026-09") == []


def test_inactive_card_still_has_projected_invoice():
    uid = user()
    item = card(uid)
    services.registrar_compra_cartao(
        uid,
        {
            "cartao_id": item["id"],
            "descricao": "Purchase",
            "valor_total": "100",
            "parcelas": "1",
            "data_compra": "2026-01-01",
        },
    )
    with db_cursor(commit=True) as cursor:
        cursor.execute("UPDATE cartoes_credito SET ativo=0 WHERE id=%s", (item["id"],))
    assert services.resumo_faturas_geral(uid, "2026-01")[0]["total"] == 100


@pytest.mark.parametrize(
    "path",
    [
        "/contas/999999",
        "/contas/999999/editar",
        "/cartoes/999999",
        "/dividas/999999/editar",
        "/caixinhas/999999/editar",
        "/categorias/999999/editar",
        "/previsoes/999999/editar",
        "/movimentacoes/999999/editar",
    ],
)
def test_missing_objects_redirect_without_server_error(authenticated_client, path):
    response = authenticated_client.get(path)
    assert response.status_code == 302


def test_http_finance_cruds_and_edit_pages(authenticated_client):
    client = authenticated_client
    with client.session_transaction() as session:
        uid = session["usuario_id"]
    csrf = token(client)

    def post(path, data):
        response = client.post(path, data={"csrf_token": csrf, **data}, follow_redirects=True)
        assert response.status_code == 200, path
        return response

    post("/contas", {"nome": "HTTP Account", "saldo_inicial": "100"})
    account = next(x for x in services.listar_contas(uid) if x["nome"] == "HTTP Account")
    assert client.get(f"/contas/{account['id']}").status_code == 200
    post(f"/contas/{account['id']}/editar", {"nome": "HTTP Account edited", "saldo_inicial": "100"})
    post("/movimentacoes", {"tipo": "despesa", "valor": "10", "descricao": "HTTP movement", "conta_id": account["id"]})
    movement = services.listar_movimentacoes(uid)[0]
    assert client.get(f"/movimentacoes/{movement['id']}/editar").status_code == 200
    post(
        f"/movimentacoes/{movement['id']}/editar",
        {"tipo": "despesa", "valor": "20", "descricao": "Edited movement", "conta_id": account["id"]},
    )
    assert saldo_conta(uid, account["id"]) == 80
    post(f"/movimentacoes/{movement['id']}/deletar", {})
    assert saldo_conta(uid, account["id"]) == 100
    post("/caixinhas", {"nome": "HTTP Goal", "valor_guardado": "50"})
    goal = services.listar_caixinhas(uid)[0]
    assert client.get(f"/caixinhas/{goal['id']}/editar").status_code == 200
    post(f"/caixinhas/{goal['id']}/editar", {"nome": "HTTP Goal edited", "valor_guardado": "50"})
    post(f"/caixinhas/{goal['id']}/movimentar", {"acao": "adicionar", "valor": "25"})
    assert services.obter_caixinha(uid, goal["id"])["valor_guardado"] == 75
    post(f"/caixinhas/{goal['id']}/deletar", {})
    assert services.listar_caixinhas(uid) == []
    credit = card(uid)
    item, _ = debt(uid)
    for path in [
        f"/contas/{account['id']}/editar",
        f"/cartoes/{credit['id']}/editar",
        f"/cartoes/{credit['id']}",
        f"/dividas/{item['id']}/editar",
    ]:
        assert client.get(path).status_code == 200, path


def test_admin_cannot_be_called_by_regular_service_user():
    first, second = user(), user("second@example.com")
    with pytest.raises(ValueError, match="administradores"):
        services.deletar_usuario_admin(first, second)
    with pytest.raises(ValueError, match="administradores"):
        services.atualizar_usuario_admin(first, second, {"nome": "Hijacked"})


def test_xss_financial_description_is_escaped(authenticated_client):
    client = authenticated_client
    response = client.post(
        "/categorias",
        data={"csrf_token": token(client), "nome": "<script>alert(1)</script>", "tipo": "geral"},
        follow_redirects=True,
    )
    assert b"<script>alert(1)</script>" not in response.data
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in response.data


def test_paid_off_debt_remains_visible_in_historical_schedule():
    uid = user()
    item, _ = debt(uid, count=1)
    month = date.today().strftime("%Y-%m")
    services.pagar_parcela_divida(uid, item["id"], month)
    assert services.obter_divida(uid, item["id"])["status"] == "quitada"
    history = services.parcelas_dividas_mes(uid, month)
    assert len(history) == 1
    assert history[0]["paga"] is True
    assert total_dividas_mes(uid, month) == Decimal("100")


def test_cancelled_debt_keeps_paid_history_without_future_obligations():
    uid = user()
    item, account = debt(uid, count=2)
    month = date.today().strftime("%Y-%m")
    next_month = somar_meses(date.today().replace(day=1), 1).strftime("%Y-%m")
    services.pagar_parcela_divida(uid, item["id"], month)
    services.salvar_divida(
        uid,
        {
            "descricao": "Example debt",
            "valor_parcela": "100",
            "parcelas_total": "2",
            "parcelas_pagas": "1",
            "data_inicio": date.today().replace(day=1).isoformat(),
            "dia_vencimento": "20",
            "conta_id": str(account["id"]),
            "ativa": "0",
        },
        item["id"],
    )
    assert services.parcelas_dividas_mes(uid, month)[0]["paga"] is True
    assert services.parcelas_dividas_mes(uid, next_month) == []


def test_card_billing_cycle_cannot_rewrite_existing_installments():
    uid = user()
    item = card(uid)
    services.registrar_compra_cartao(
        uid,
        {"cartao_id": item["id"], "descricao": "Historical purchase",
         "valor_total": "90", "parcelas": "3", "data_compra": "2026-01-10"},
    )
    jan = services.parcelas_cartao_mes(uid, "2026-01", item["id"])
    assert jan[0]["valor"] == Decimal("30")
    with pytest.raises(ValueError, match="alterar o fechamento ou vencimento"):
        services.salvar_cartao(
            uid,
            {"nome": "Changed", "limite_total": "1000", "dia_fechamento": "5", "dia_vencimento": "18"},
            item["id"],
        )
    with pytest.raises(ValueError, match="possui compras"):
        services.deletar_cartao(uid, item["id"])
    assert services.obter_cartao(uid, item["id"])["dia_fechamento"] == 10
    services.salvar_cartao(
        uid,
        {"nome": "Renamed", "limite_total": "1200", "dia_fechamento": "10", "dia_vencimento": "18", "ativo": "0"},
        item["id"],
    )
    updated_jan = services.parcelas_cartao_mes(uid, "2026-01", item["id"])
    assert [(p["valor"], p["vencimento"]) for p in updated_jan] == [
        (p["valor"], p["vencimento"]) for p in jan
    ]
    assert services.obter_cartao(uid, item["id"])["ativo"] == 0


def test_list_accounts_aggregates_balances_without_leaking_other_users():
    first, second = user(), user("independent@example.com")
    a = next(x for x in services.listar_contas(first) if x["nome"] == "Conta principal")
    b = next(x for x in services.listar_contas(second) if x["nome"] == "Conta principal")
    services.salvar_movimentacao(
        first, {"tipo": "receita", "valor": "200", "descricao": "Credit", "conta_id": a["id"]}
    )
    services.salvar_movimentacao(
        first, {"tipo": "despesa", "valor": "35.50", "descricao": "Debit", "conta_id": a["id"]}
    )
    services.salvar_movimentacao(
        second, {"tipo": "receita", "valor": "999", "descricao": "Private", "conta_id": b["id"]}
    )
    balances = {a["nome"]: a["saldo_atual"] for a in services.listar_contas(first)}
    assert balances["Conta principal"] == Decimal("164.50")
    assert balances["Carteira"] == Decimal("0.00")


def test_bootstrap_admin_is_explicit_and_idempotent(app, monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_USER_ENABLED", "true")
    monkeypatch.setenv("BOOTSTRAP_USER_NAME", "Maintainer")
    monkeypatch.setenv("BOOTSTRAP_USER_EMAIL", "maintainer@example.com")
    monkeypatch.setenv("BOOTSTRAP_USER_PASSWORD", "AdminStrong123")
    runner = app.test_cli_runner()
    result = runner.invoke(args=["bootstrap-user", "--if-enabled", "--admin"])
    assert result.exit_code == 0, result.output
    admin = services.obter_usuario_por_email("maintainer@example.com")
    assert admin["nivel_acesso"] == "ADMIN"
    assert usuario_e_admin(admin["id"]) is True
    assert runner.invoke(args=["bootstrap-user", "--if-enabled"]).exit_code == 0
    assert services.obter_usuario_por_email("maintainer@example.com")["nivel_acesso"] == "ADMIN"
    assert services.criar_usuario("Ordinary", "ordinary@example.com", "StrongPass123")
    assert services.obter_usuario_por_email("ordinary@example.com")["nivel_acesso"] == "USER"


def test_card_summaries_are_consistent_across_multiple_cards():
    uid = user()
    first = card(uid)
    services.salvar_cartao(
        uid, {"nome": "Other card", "limite_total": "900",
              "dia_fechamento": "8", "dia_vencimento": "15"}
    )
    second = next(c for c in services.listar_cartoes(uid) if c["nome"] == "Other card")
    services.registrar_compra_cartao(
        uid, {"cartao_id": first["id"], "descricao": "First", "valor_total": "90",
              "parcelas": "3", "data_compra": "2026-01-01"}
    )
    services.registrar_compra_cartao(
        uid, {"cartao_id": second["id"], "descricao": "Second", "valor_total": "25",
              "parcelas": "1", "data_compra": "2026-01-01"}
    )
    summary = services.resumo_faturas_geral(uid, "2026-01", meses=3)
    assert [s["total"] for s in summary] == [
        Decimal("55"), Decimal("30"), Decimal("30")
    ]
    totals = services.listar_cartoes(uid, ano_mes="2026-01")
    by_id = {c["id"]: c for c in totals}
    assert by_id[first["id"]]["fatura_atual"] == Decimal("30")
    assert by_id[second["id"]]["fatura_atual"] == Decimal("25")
    assert sum((p["valor"] for p in services.parcelas_cartao_mes(uid, "2026-01")), Decimal("0")) == Decimal("55")
