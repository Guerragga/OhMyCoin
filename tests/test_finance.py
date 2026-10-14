from datetime import date
from decimal import Decimal

import pytest

from app import services
from database import db_cursor


def create_user(email):
    return services.criar_usuario("User", email, "StrongPass123")


def test_account_isolation_between_users():
    first = create_user("first@example.com")
    second = create_user("second@example.com")

    accounts = services.listar_contas(first)
    account_id = accounts[0]["id"]

    with pytest.raises(ValueError, match="Conta não encontrada"):
        services.obter_conta(second, account_id)


def test_account_transaction_updates_balance():
    user_id = create_user("balance@example.com")
    account = services.listar_contas(user_id)[0]

    services.salvar_movimentacao(
        user_id,
        {
            "tipo": "receita",
            "valor": "1000,00",
            "descricao": "Test income",
            "data_movimentacao": date.today().isoformat(),
            "conta_id": str(account["id"]),
            "forma_pagamento": "conta",
        },
    )

    refreshed = services.obter_conta(user_id, account["id"])
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT c.saldo_inicial +
                   COALESCE(SUM(CASE WHEN m.tipo='receita' THEN m.valor ELSE -m.valor END), 0) AS saldo
            FROM contas c
            LEFT JOIN movimentacoes m ON m.conta_id=c.id
            WHERE c.id=%s AND c.usuario_id=%s
            GROUP BY c.id, c.saldo_inicial
            """,
            (account["id"], user_id),
        )
        saldo = Decimal(cursor.fetchone()["saldo"])

    assert refreshed["id"] == account["id"]
    assert saldo >= Decimal("1000.00")


def test_card_installments_are_projected_without_duplicate_real_movement():
    user_id = create_user("card@example.com")
    categories = services.listar_categorias(user_id, "despesa")
    category_id = categories[0]["id"] if categories else None

    services.salvar_cartao(
        user_id,
        {
            "nome": "Test Card",
            "bandeira": "Visa",
            "limite_total": "3000",
            "dia_fechamento": "10",
            "dia_vencimento": "18",
            "ativo": "1",
        },
    )
    card = services.listar_cartoes(user_id)[0]

    services.registrar_compra_cartao(
        user_id,
        {
            "cartao_id": str(card["id"]),
            "descricao": "Installment purchase",
            "valor_total": "600",
            "parcelas": "3",
            "data_compra": date.today().isoformat(),
            "categoria_id": str(category_id) if category_id else "",
        },
    )

    purchases = services.listar_compras_cartao(user_id, card["id"])
    assert len(purchases) == 1
    assert Decimal(purchases[0]["valor_parcela"]) == Decimal("200.00")

    movements = services.listar_movimentacoes(user_id, {})
    card_movements = [item for item in movements if item.get("entidade") == "compra_cartao"]
    assert len(card_movements) == 1


def test_debt_payment_creates_single_expense_movement():
    user_id = create_user("debt@example.com")
    account = services.listar_contas(user_id)[0]

    services.salvar_divida(
        user_id,
        {
            "descricao": "Test debt",
            "credor": "Example",
            "valor_total": "1200",
            "valor_parcela": "100",
            "parcelas_total": "12",
            "parcelas_pagas": "0",
            "data_inicio": date.today().replace(day=1).isoformat(),
            "dia_vencimento": "20",
            "conta_id": str(account["id"]),
            "ativa": "1",
        },
    )
    debt = services.listar_dividas(user_id)[0]
    current_month = date.today().strftime("%Y-%m")

    services.pagar_parcela_divida(user_id, debt["id"], current_month)

    with db_cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS total FROM movimentacoes WHERE usuario_id=%s AND origem='divida'",
            (user_id,),
        )
        assert cursor.fetchone()["total"] == 1


def test_card_installment_rounding_reconciles_to_total():
    user_id = create_user("rounding@example.com")
    services.salvar_cartao(
        user_id,
        {
            "nome": "Rounding Card",
            "limite_total": "1000",
            "dia_fechamento": "10",
            "dia_vencimento": "18",
            "ativo": "1",
        },
    )
    card = services.listar_cartoes(user_id)[0]
    services.registrar_compra_cartao(
        user_id,
        {
            "cartao_id": str(card["id"]),
            "descricao": "Rounding purchase",
            "valor_total": "100",
            "parcelas": "3",
            "data_compra": date.today().isoformat(),
        },
    )

    from app.services.cards import meses_a_partir

    total = Decimal("0.00")
    for month in meses_a_partir(date.today().strftime("%Y-%m"), 4):
        total += sum(
            (Decimal(item["valor"]) for item in services.parcelas_cartao_mes(user_id, month, card["id"])),
            Decimal("0.00"),
        )

    assert total == Decimal("100.00")


def test_fully_paid_debt_is_not_left_active():
    user_id = create_user("paid-debt@example.com")
    account = services.listar_contas(user_id)[0]

    services.salvar_divida(
        user_id,
        {
            "descricao": "Paid debt",
            "valor_parcela": "100",
            "parcelas_total": "2",
            "parcelas_pagas": "2",
            "data_inicio": date.today().replace(day=1).isoformat(),
            "dia_vencimento": "20",
            "conta_id": str(account["id"]),
            "ativa": "1",
        },
    )

    debt = services.listar_dividas(user_id)[0]
    assert not debt["ativa"]
    assert debt["status"] == "quitada"


def test_recurring_forecast_does_not_appear_before_start_month():
    from app.services.common import somar_meses

    user_id = create_user("forecast@example.com")
    account = services.listar_contas(user_id)[0]
    current_start = date.today().replace(day=1)
    next_month = somar_meses(current_start, 1).strftime("%Y-%m")
    current_month = current_start.strftime("%Y-%m")

    services.salvar_previsao(
        user_id,
        {
            "ano_mes": next_month,
            "tipo": "receita",
            "descricao": "Future recurring income",
            "valor_previsto": "1000",
            "dia_previsto": "5",
            "conta_id": str(account["id"]),
            "recorrente": "1",
        },
    )

    assert not any(
        item["descricao"] == "Future recurring income" for item in services.listar_previsoes(user_id, current_month)
    )
    assert any(
        item["descricao"] == "Future recurring income" for item in services.listar_previsoes(user_id, next_month)
    )


def test_savings_rejects_unknown_movement_action():
    user_id = create_user("savings@example.com")
    services.salvar_caixinha(
        user_id,
        {
            "nome": "Goal",
            "valor_guardado": "100",
            "meta": "1000",
            "aporte_mensal": "100",
            "data_inicio": date.today().isoformat(),
        },
    )
    savings = services.listar_caixinhas(user_id)[0]

    with pytest.raises(ValueError, match="Ação inválida"):
        services.movimentar_caixinha(user_id, savings["id"], "50", "invalid")


def test_early_debt_payment_is_included_in_current_category_analytics():
    from app.services.common import somar_meses
    from app.services.dashboard import despesas_por_categoria

    user_id = create_user("early-debt@example.com")
    account = services.listar_contas(user_id)[0]
    debt_category = next(item for item in services.listar_categorias(user_id, "despesa") if item["nome"] == "Dívidas")
    next_month_start = somar_meses(date.today().replace(day=1), 1)

    services.salvar_divida(
        user_id,
        {
            "descricao": "Future installment",
            "credor": "Example",
            "valor_parcela": "250",
            "parcelas_total": "4",
            "parcelas_pagas": "0",
            "data_inicio": next_month_start.isoformat(),
            "dia_vencimento": "20",
            "categoria_id": str(debt_category["id"]),
            "conta_id": str(account["id"]),
            "ativa": "1",
        },
    )
    debt = services.listar_dividas(user_id)[0]
    services.antecipar_proxima_parcela_divida(user_id, debt["id"])

    categories = despesas_por_categoria(user_id, date.today().strftime("%Y-%m"))
    debt_total = next(Decimal(str(item["total"])) for item in categories if item["categoria"] == "Dívidas")
    assert debt_total == Decimal("250.0")
