from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from database import db_cursor
from .accounts import validar_conta
from .categories import validar_categoria
from .common import (
    data_por_dia,
    decimal_brl,
    hoje,
    inicio_fim_mes,
    inteiro,
    normalizar_mes,
    parse_data,
    somar_meses,
    texto_obrigatorio,
    texto_opcional,
)


def salvar_divida(usuario_id, form, divida_id=None):
    descricao = texto_obrigatorio(form.get("descricao"), "Descrição", 160)
    credor = texto_opcional(form.get("credor"), 120)
    valor_parcela = decimal_brl(form.get("valor_parcela"), "Valor da parcela")
    parcelas_total = inteiro(form.get("parcelas_total") or 1, "Total de parcelas", 1, 600)
    parcelas_pagas = inteiro(form.get("parcelas_pagas") or 0, "Parcelas pagas", 0, parcelas_total)
    data_inicio = parse_data(form.get("data_inicio"), hoje())
    dia_vencimento = inteiro(form.get("dia_vencimento") or 1, "Dia de vencimento", 1, 31)
    categoria_id = validar_categoria(usuario_id, form.get("categoria_id"), "despesa")
    conta_id = validar_conta(usuario_id, form.get("conta_id"))
    ativa = 1 if form.get("ativa", "1") == "1" else 0
    quitada = parcelas_pagas >= parcelas_total
    if quitada:
        ativa = 0
    status = "quitada" if quitada else ("ativa" if ativa else "cancelada")
    observacao = texto_opcional(form.get("observacao"), 1000)
    valor_total = decimal_brl(valor_parcela * parcelas_total, "Valor total")
    with db_cursor(commit=True) as cursor:
        if divida_id:
            cursor.execute("SELECT * FROM dividas WHERE id=%s AND usuario_id=%s FOR UPDATE", (divida_id, usuario_id))
            existing = cursor.fetchone()
            if not existing:
                raise ValueError("Dívida não encontrada.")
            cursor.execute(
                "SELECT id FROM pagamentos_dividas WHERE divida_id=%s AND usuario_id=%s LIMIT 1",
                (divida_id, usuario_id),
            )
            if cursor.fetchone() and (
                valor_parcela != existing["valor_parcela"]
                or parcelas_total != existing["parcelas_total"]
                or parcelas_pagas != existing["parcelas_pagas"]
                or data_inicio != existing["data_inicio"]
                or dia_vencimento != existing["dia_vencimento"]
            ):
                raise ValueError("Estorne os pagamentos antes de alterar parcelas, valores ou datas da dívida.")
            cursor.execute(
                """
                UPDATE dividas SET descricao=%s, credor=%s, valor_total=%s, saldo_devedor=%s, taxa_juros=0, status=%s, valor_parcela=%s, parcelas_total=%s,
                    parcelas_pagas=%s, data_inicio=%s, dia_vencimento=%s, categoria_id=%s, conta_id=%s, ativa=%s, observacao=%s
                WHERE id=%s AND usuario_id=%s
                """,
                (
                    descricao,
                    credor,
                    valor_total,
                    max(Decimal("0.00"), valor_total - (valor_parcela * Decimal(parcelas_pagas))),
                    status,
                    valor_parcela,
                    parcelas_total,
                    parcelas_pagas,
                    data_inicio,
                    dia_vencimento,
                    categoria_id,
                    conta_id,
                    ativa,
                    observacao,
                    divida_id,
                    usuario_id,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO dividas (usuario_id, descricao, credor, valor_total, saldo_devedor, taxa_juros, status, valor_parcela, parcelas_total, parcelas_pagas,
                    data_inicio, dia_vencimento, categoria_id, conta_id, ativa, observacao)
                VALUES (%s,%s,%s,%s,%s,0,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    usuario_id,
                    descricao,
                    credor,
                    valor_total,
                    max(Decimal("0.00"), valor_total - (valor_parcela * Decimal(parcelas_pagas))),
                    status,
                    valor_parcela,
                    parcelas_total,
                    parcelas_pagas,
                    data_inicio,
                    dia_vencimento,
                    categoria_id,
                    conta_id,
                    ativa,
                    observacao,
                ),
            )


def obter_divida(usuario_id, divida_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM dividas WHERE id=%s AND usuario_id=%s", (divida_id, usuario_id))
        divida = cursor.fetchone()
    if not divida:
        raise ValueError("Dívida não encontrada.")
    return divida


def deletar_divida(usuario_id, divida_id):
    obter_divida(usuario_id, divida_id)
    with db_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM dividas WHERE id=%s AND usuario_id=%s", (divida_id, usuario_id))


def _pagamentos_divida(usuario_id, divida_id=None):
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT divida_id, parcela_numero, ano_mes, data_pagamento, movimentacao_id
            FROM pagamentos_dividas
            WHERE usuario_id=%s AND (%s IS NULL OR divida_id=%s)
            """,
            (usuario_id, divida_id, divida_id),
        )
        return cursor.fetchall()


def parcelas_pagas_set(usuario_id, divida):
    return _paid_numbers(divida, _pagamentos_divida(usuario_id, divida["id"]))


def _paid_numbers(divida, pagamentos):
    recorded = {int(row["parcela_numero"]) for row in pagamentos}
    imported_count = max(0, int(divida.get("parcelas_pagas") or 0) - len(recorded))
    return recorded | set(range(1, imported_count + 1))


def data_vencimento_parcela_divida(divida, parcela_numero: int) -> date:
    base = divida["data_inicio"].replace(day=1)
    mes_parcela = somar_meses(base, int(parcela_numero) - 1).strftime("%Y-%m")
    return data_por_dia(mes_parcela, int(divida["dia_vencimento"] or 1))


def parcela_divida_no_mes(divida, ano_mes):
    alvo = datetime.strptime(normalizar_mes(ano_mes) + "-01", "%Y-%m-%d").date()
    inicio = divida["data_inicio"].replace(day=1)
    diff = (alvo.year - inicio.year) * 12 + (alvo.month - inicio.month)
    if diff < 0 or diff >= int(divida["parcelas_total"]):
        return None
    parcela_numero = diff + 1
    vencimento = data_por_dia(ano_mes, divida["dia_vencimento"])
    return {
        "divida_id": divida["id"],
        "descricao": divida["descricao"],
        "credor": divida.get("credor"),
        "valor": Decimal(divida["valor_parcela"]),
        "parcela_numero": parcela_numero,
        "parcelas_total": divida["parcelas_total"],
        "vencimento": vencimento,
        "categoria_id": divida.get("categoria_id"),
        "categoria_nome": divida.get("categoria_nome"),
        "conta_id": divida.get("conta_id"),
        "conta_nome": divida.get("conta_nome"),
        "paga": False,
        "paga_antecipada": False,
        "data_pagamento": None,
    }


def parcelas_dividas_mes(usuario_id, ano_mes):
    ano_mes = normalizar_mes(ano_mes)
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT d.*, c.nome AS categoria_nome, ct.nome AS conta_nome
            FROM dividas d
            LEFT JOIN categorias c ON c.id=d.categoria_id
            LEFT JOIN contas ct ON ct.id=d.conta_id
            WHERE d.usuario_id=%s AND d.ativa=1
            """,
            (usuario_id,),
        )
        dividas = cursor.fetchall()
    pagamentos = {}
    for r in _pagamentos_divida(usuario_id):
        pagamentos[(r["divida_id"], int(r["parcela_numero"]))] = r
    parcelas = []
    for divida in dividas:
        p = parcela_divida_no_mes(divida, ano_mes)
        if not p:
            continue
        pagamento = pagamentos.get((p["divida_id"], p["parcela_numero"]))
        paid = _paid_numbers(divida, [r for (debt_id, _), r in pagamentos.items() if debt_id == divida["id"]])
        pagas_legado = p["parcela_numero"] in paid
        if pagamento or pagas_legado:
            data_pagamento = pagamento.get("data_pagamento") if pagamento else None
            p["paga"] = True
            p["data_pagamento"] = data_pagamento
            if data_pagamento and data_pagamento.strftime("%Y-%m") < ano_mes:
                p["paga_antecipada"] = True
        parcelas.append(p)
    return parcelas


def proxima_parcela_aberta_divida(usuario_id, divida):
    pagas = parcelas_pagas_set(usuario_id, divida)
    for numero in range(1, int(divida["parcelas_total"] or 0) + 1):
        if numero not in pagas:
            return numero
    return None


def _registrar_pagamento_parcela_divida(usuario_id, divida, parcela_numero, data_pagamento=None):
    data_pagamento = data_pagamento or hoje()
    with db_cursor(commit=True) as cursor:
        cursor.execute("SELECT * FROM dividas WHERE id=%s AND usuario_id=%s FOR UPDATE", (divida["id"], usuario_id))
        divida = cursor.fetchone()
        if not divida or not divida["ativa"]:
            raise ValueError("Dívida inativa ou não encontrada.")
        parcela_numero = inteiro(parcela_numero, "Parcela", 1, divida["parcelas_total"])
        cursor.execute(
            "SELECT parcela_numero FROM pagamentos_dividas WHERE usuario_id=%s AND divida_id=%s",
            (usuario_id, divida["id"]),
        )
        if parcela_numero in _paid_numbers(divida, cursor.fetchall()):
            raise ValueError("Essa parcela já está marcada como paga.")
        vencimento = data_vencimento_parcela_divida(divida, parcela_numero)
        ano_mes_vencimento = vencimento.strftime("%Y-%m")
        descricao = f"Dívida: {divida['descricao']} ({parcela_numero}/{divida['parcelas_total']})"
        cursor.execute(
            """
            INSERT INTO movimentacoes (usuario_id, tipo, valor, descricao, data_movimentacao, categoria_id, conta_id, forma_pagamento, origem, referencia_id)
            VALUES (%s,'despesa',%s,%s,%s,%s,%s,'conta','divida',%s)
            """,
            (
                usuario_id,
                divida["valor_parcela"],
                descricao,
                data_pagamento,
                divida.get("categoria_id"),
                divida.get("conta_id"),
                divida["id"],
            ),
        )
        mov_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO pagamentos_dividas (usuario_id, divida_id, parcela_numero, ano_mes, data_pagamento, movimentacao_id)
            VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (usuario_id, divida["id"], parcela_numero, ano_mes_vencimento, data_pagamento, mov_id),
        )
        cursor.execute(
            """
            UPDATE dividas
            SET parcelas_pagas = LEAST(parcelas_total, parcelas_pagas + 1),
                saldo_devedor = GREATEST(0, saldo_devedor - valor_parcela)
            WHERE id=%s AND usuario_id=%s
            """,
            (divida["id"], usuario_id),
        )
        cursor.execute(
            "UPDATE dividas SET ativa = IF(parcelas_pagas >= parcelas_total, 0, ativa), status = IF(parcelas_pagas >= parcelas_total, 'quitada', status) WHERE id=%s AND usuario_id=%s",
            (divida["id"], usuario_id),
        )


def pagar_parcela_divida(usuario_id, divida_id, ano_mes):
    ano_mes = normalizar_mes(ano_mes)
    divida = obter_divida(usuario_id, divida_id)
    p = parcela_divida_no_mes(divida, ano_mes)
    if not p:
        raise ValueError("Essa dívida não possui parcela neste mês.")
    _registrar_pagamento_parcela_divida(usuario_id, divida, p["parcela_numero"], hoje())


def antecipar_proxima_parcela_divida(usuario_id, divida_id):
    divida = obter_divida(usuario_id, divida_id)
    numero = proxima_parcela_aberta_divida(usuario_id, divida)
    if not numero:
        raise ValueError("Essa dívida já está quitada.")
    _registrar_pagamento_parcela_divida(usuario_id, divida, numero, hoje())
    return numero


def listar_dividas(usuario_id):
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT d.*, c.nome AS categoria_nome, ct.nome AS conta_nome
            FROM dividas d
            LEFT JOIN categorias c ON c.id=d.categoria_id
            LEFT JOIN contas ct ON ct.id=d.conta_id
            WHERE d.usuario_id=%s
            ORDER BY d.ativa DESC, d.data_inicio DESC
            """,
            (usuario_id,),
        )
        dividas = cursor.fetchall()
    for d in dividas:
        pagas = max(int(d.get("parcelas_pagas") or 0), len(parcelas_pagas_set(usuario_id, d)))
        total = int(d["parcelas_total"] or 1)
        abertas = max(0, total - pagas)
        d["parcelas_pagas"] = pagas
        d["saldo_estimado"] = Decimal(d["valor_parcela"] or 0) * Decimal(abertas)
        d["saldo_devedor"] = d["saldo_estimado"]
        d["progresso"] = round((pagas / max(1, total)) * 100, 1)
        proxima = proxima_parcela_aberta_divida(usuario_id, d)
        d["proxima_parcela"] = proxima
        d["proximo_vencimento"] = data_vencimento_parcela_divida(d, proxima) if proxima else None
    return dividas


def total_dividas_pagas_no_mes(usuario_id, ano_mes):
    _, inicio, fim = inicio_fim_mes(ano_mes)
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT COALESCE(SUM(m.valor), 0) AS total
            FROM movimentacoes m
            WHERE m.usuario_id=%s AND m.origem='divida'
              AND m.data_movimentacao >= %s AND m.data_movimentacao < %s
            """,
            (usuario_id, inicio, fim),
        )
        return Decimal(cursor.fetchone()["total"] or 0)


def total_dividas_mes(usuario_id, ano_mes):
    # Pagamentos feitos no mês + parcelas vencendo no mês ainda não pagas.
    pagas_no_mes = total_dividas_pagas_no_mes(usuario_id, ano_mes)
    abertas_no_mes = sum(
        (Decimal(p["valor"] or 0) for p in parcelas_dividas_mes(usuario_id, ano_mes) if not p.get("paga")),
        Decimal("0.00"),
    )
    return pagas_no_mes + abertas_no_mes
