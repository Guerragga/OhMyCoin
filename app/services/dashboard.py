from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from database import db_cursor
from .accounts import listar_contas
from .cards import compromisso_cartao, alertas_cartoes, listar_cartoes, parcelas_cartao_mes, resumo_faturas_geral
from .common import hoje, inicio_fim_mes, normalizar_mes, somar_meses
from .debts import listar_dividas, parcelas_dividas_mes, total_dividas_mes
from .forecasts import listar_previsoes
from .savings import listar_caixinhas
from .transactions import listar_movimentacoes
from .users import configuracoes_usuario


def soma_movimentacoes(usuario_id, ano_mes, tipo=None):
    _, inicio, fim = inicio_fim_mes(ano_mes)
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT COALESCE(SUM(valor),0) AS total FROM movimentacoes WHERE usuario_id=%s "
            "AND data_movimentacao >= %s AND data_movimentacao < %s AND (%s IS NULL OR tipo=%s)",
            (usuario_id, inicio, fim, tipo, tipo),
        )
        return Decimal(cursor.fetchone()["total"] or 0)


def soma_movimentacoes_conta(usuario_id, ano_mes, tipo=None, incluir_dividas=False):
    _, inicio, fim = inicio_fim_mes(ano_mes)
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT COALESCE(SUM(valor),0) AS total FROM movimentacoes WHERE usuario_id=%s "
            "AND data_movimentacao >= %s AND data_movimentacao < %s AND forma_pagamento='conta' "
            "AND (%s IS NULL OR tipo=%s) AND (%s=1 OR origem <> 'divida')",
            (usuario_id, inicio, fim, tipo, tipo, int(incluir_dividas)),
        )
        return Decimal(cursor.fetchone()["total"] or 0)


def somar_investimentos(usuario_id):
    # Investment accounts are already included in saldo_contas.
    return Decimal("0.00")


def saldo_devedor_dividas(usuario_id):
    return sum(
        (Decimal(d.get("saldo_estimado") or 0) for d in listar_dividas(usuario_id) if d.get("ativa")), Decimal("0.00")
    )


def despesas_por_categoria(usuario_id, ano_mes):
    _, inicio, fim = inicio_fim_mes(ano_mes)
    totais = {}

    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT COALESCE(c.nome, 'Sem categoria') AS categoria, COALESCE(SUM(m.valor),0) AS total
            FROM movimentacoes m
            LEFT JOIN categorias c ON c.id=m.categoria_id
            WHERE m.usuario_id=%s AND m.tipo='despesa' AND m.forma_pagamento='conta'
              AND m.origem <> 'divida' AND m.data_movimentacao >= %s AND m.data_movimentacao < %s
            GROUP BY COALESCE(c.nome, 'Sem categoria')
            """,
            (usuario_id, inicio, fim),
        )
        for row in cursor.fetchall():
            totais[row["categoria"]] = totais.get(row["categoria"], Decimal("0.00")) + Decimal(row["total"] or 0)

        cursor.execute(
            """
            SELECT COALESCE(c.nome, 'Dívidas') AS categoria, COALESCE(SUM(m.valor),0) AS total
            FROM movimentacoes m
            LEFT JOIN categorias c ON c.id=m.categoria_id
            WHERE m.usuario_id=%s AND m.tipo='despesa' AND m.origem='divida'
              AND m.data_movimentacao >= %s AND m.data_movimentacao < %s
            GROUP BY COALESCE(c.nome, 'Dívidas')
            """,
            (usuario_id, inicio, fim),
        )
        for row in cursor.fetchall():
            totais[row["categoria"]] = totais.get(row["categoria"], Decimal("0.00")) + Decimal(row["total"] or 0)

    for item in parcelas_cartao_mes(usuario_id, ano_mes):
        nome = item.get("categoria_nome") or "Cartão sem categoria"
        totais[nome] = totais.get(nome, Decimal("0.00")) + Decimal(item["valor"] or 0)

    # Only projected/open debt installments are added here. Paid installments
    # are already represented by real debt movements above, including early payments.
    for item in parcelas_dividas_mes(usuario_id, ano_mes):
        if item.get("paga"):
            continue
        nome = item.get("categoria_nome") or "Dívidas"
        totais[nome] = totais.get(nome, Decimal("0.00")) + Decimal(item["valor"] or 0)

    return [
        {"categoria": name, "total": float(total)}
        for name, total in sorted(totais.items(), key=lambda item: item[1], reverse=True)[:10]
    ]


def despesas_por_forma_pagamento(usuario_id, ano_mes):
    conta = soma_movimentacoes_conta(usuario_id, ano_mes, "despesa", incluir_dividas=False)
    cartao = sum((Decimal(p["valor"] or 0) for p in parcelas_cartao_mes(usuario_id, ano_mes)), Decimal("0.00"))
    dividas = total_dividas_mes(usuario_id, ano_mes)
    return [
        {"forma": "Conta/Carteira", "total": float(conta)},
        {"forma": "Cartão", "total": float(cartao)},
        {"forma": "Dívidas", "total": float(dividas)},
    ]


def despesas_por_conta(usuario_id, ano_mes):
    _, inicio, fim = inicio_fim_mes(ano_mes)
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT COALESCE(ct.nome, 'Sem conta') AS conta, COALESCE(SUM(m.valor),0) AS total
            FROM movimentacoes m
            LEFT JOIN contas ct ON ct.id=m.conta_id
            WHERE m.usuario_id=%s AND m.tipo='despesa' AND m.forma_pagamento='conta'
              AND m.data_movimentacao >= %s AND m.data_movimentacao < %s
            GROUP BY COALESCE(ct.nome, 'Sem conta')
            ORDER BY total DESC
            LIMIT 8
            """,
            (usuario_id, inicio, fim),
        )
        return [{"conta": r["conta"], "total": float(r["total"] or 0)} for r in cursor.fetchall()]


def despesas_por_cartao(usuario_id, ano_mes):
    totais = {}
    for p in parcelas_cartao_mes(usuario_id, ano_mes):
        totais[p["cartao_nome"]] = totais.get(p["cartao_nome"], Decimal("0.00")) + Decimal(p["valor"] or 0)
    return [
        {"cartao": k, "total": float(v)} for k, v in sorted(totais.items(), key=lambda item: item[1], reverse=True)[:8]
    ]


def serie_mensal(usuario_id, ano_mes, meses=6):
    ano_mes = normalizar_mes(ano_mes)
    base = datetime.strptime(ano_mes + "-01", "%Y-%m-%d").date()
    labels, receitas, despesas, saldos = [], [], [], []
    for i in range(meses - 1, -1, -1):
        mes_ref = somar_meses(base, -i).strftime("%Y-%m")
        rec = soma_movimentacoes(usuario_id, mes_ref, "receita")
        desp_conta = soma_movimentacoes_conta(usuario_id, mes_ref, "despesa", incluir_dividas=False)
        desp_cartao = sum((Decimal(p["valor"] or 0) for p in parcelas_cartao_mes(usuario_id, mes_ref)), Decimal("0.00"))
        desp_dividas = total_dividas_mes(usuario_id, mes_ref)
        desp = desp_conta + desp_cartao + desp_dividas
        labels.append(mes_ref)
        receitas.append(float(rec))
        despesas.append(float(desp))
        saldos.append(float(rec - desp))
    return {"labels": labels, "receitas": receitas, "despesas": despesas, "saldos": saldos}


def obter_resumo_dashboard(usuario_id, ano_mes=None):
    ano_mes, inicio, fim = inicio_fim_mes(ano_mes)
    receitas_reais = soma_movimentacoes(usuario_id, ano_mes, "receita")
    despesas_conta = soma_movimentacoes_conta(usuario_id, ano_mes, "despesa", incluir_dividas=False)
    parcelas_cartao = parcelas_cartao_mes(usuario_id, ano_mes)
    total_cartao_mes = sum((Decimal(p["valor"] or 0) for p in parcelas_cartao), Decimal("0.00"))
    parcelas_dividas = parcelas_dividas_mes(usuario_id, ano_mes)
    total_dividas_mes_valor = total_dividas_mes(usuario_id, ano_mes)
    despesas_comprometidas = despesas_conta + total_cartao_mes + total_dividas_mes_valor
    despesas_reais = soma_movimentacoes_conta(usuario_id, ano_mes, "despesa", incluir_dividas=True)

    previsoes = listar_previsoes(usuario_id, ano_mes)
    previsao_receitas = sum(
        (Decimal(p["valor_previsto"]) for p in previsoes if p["tipo"] == "receita"), Decimal("0.00")
    )
    previsao_despesas = sum(
        (Decimal(p["valor_previsto"]) for p in previsoes if p["tipo"] == "despesa"), Decimal("0.00")
    )

    contas = listar_contas(usuario_id)
    saldo_contas = sum((Decimal(c["saldo_atual"] or 0) for c in contas), Decimal("0.00"))
    caixinhas = listar_caixinhas(usuario_id)
    total_caixinhas = sum((Decimal(c["valor_guardado"] or 0) for c in caixinhas), Decimal("0.00"))
    total_investimentos = somar_investimentos(usuario_id)
    capital_geral = saldo_contas + total_caixinhas + total_investimentos
    total_dividas_abertas = saldo_devedor_dividas(usuario_id)
    compromissos_cartao = compromisso_cartao(usuario_id, hoje().strftime("%Y-%m"))
    patrimonio_liquido = capital_geral - total_dividas_abertas - compromissos_cartao

    saidas_previstas_total = (
        previsao_despesas
        + total_cartao_mes
        + sum((Decimal(p["valor"] or 0) for p in parcelas_dividas if not p.get("paga_antecipada")), Decimal("0.00"))
    )
    entradas_previstas_total = previsao_receitas
    saldo_previsto_mes = entradas_previstas_total - saidas_previstas_total
    saldo_real_mes = receitas_reais - despesas_reais
    gap_planejado_real = saldo_real_mes - saldo_previsto_mes

    alertas = alertas_cartoes(usuario_id)
    for p in parcelas_dividas:
        if not p["paga"] and 0 <= (p["vencimento"] - hoje()).days <= 7:
            alertas.append(f"Parcela de {p['descricao']} vence em {(p['vencimento'] - hoje()).days} dia(s).")

    return {
        "ano_mes": ano_mes,
        "receitas_reais": receitas_reais,
        "despesas_reais": despesas_reais,
        "despesas_comprometidas": despesas_comprometidas,
        "compromissos_cartao": compromissos_cartao,
        "despesas_conta": despesas_conta,
        "saldo_real_mes": saldo_real_mes,
        "entradas_previstas": entradas_previstas_total,
        "saidas_previstas": saidas_previstas_total,
        "saldo_previsto_mes": saldo_previsto_mes,
        "previsao_despesas": previsao_despesas,
        "total_dividas_mes": total_dividas_mes_valor,
        "total_cartao_mes": total_cartao_mes,
        "saldo_contas": saldo_contas,
        "total_caixinhas": total_caixinhas,
        "total_investimentos": total_investimentos,
        "capital_geral": capital_geral,
        "total_dividas_abertas": total_dividas_abertas,
        "patrimonio_liquido": patrimonio_liquido,
        "gap_planejado_real": gap_planejado_real,
        "categorias": despesas_por_categoria(usuario_id, ano_mes),
        "forma_pagamento": despesas_por_forma_pagamento(usuario_id, ano_mes),
        "contas_grafico": despesas_por_conta(usuario_id, ano_mes),
        "cartoes_grafico": despesas_por_cartao(usuario_id, ano_mes),
        "serie_mensal": serie_mensal(usuario_id, ano_mes, 6),
        "previsoes": previsoes,
        "parcelas_dividas": parcelas_dividas,
        "parcelas_cartao": parcelas_cartao,
        "faturas_geral": resumo_faturas_geral(usuario_id, ano_mes, 4),
        "alertas": alertas,
        "ultimas_movimentacoes": listar_movimentacoes(usuario_id, {"inicio": inicio, "fim": fim})[:10],
        "cartoes": listar_cartoes(usuario_id, apenas_ativos=True, ano_mes=ano_mes),
        "config": configuracoes_usuario(usuario_id),
    }
