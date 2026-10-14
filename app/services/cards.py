from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_DOWN

from database import db_cursor
from .common import (
    data_por_dia,
    decimal_brl,
    hoje,
    inteiro,
    mes_atual,
    normalizar_mes,
    parse_data,
    somar_meses,
    texto_obrigatorio,
    texto_opcional,
    validar_url_imagem,
)
from .categories import validar_categoria


def salvar_cartao(usuario_id, form, cartao_id=None):
    nome = texto_obrigatorio(form.get("nome"), "Nome", 100)
    bandeira = texto_opcional(form.get("bandeira"), 40)
    limite_total = decimal_brl(form.get("limite_total"), "Limite")
    dia_fechamento = inteiro(form.get("dia_fechamento") or 1, "Dia de fechamento", 1, 31)
    dia_vencimento = inteiro(form.get("dia_vencimento") or 10, "Dia de vencimento", 1, 31)
    imagem_url = validar_url_imagem(form.get("imagem_url"))
    ativo = 1 if form.get("ativo", "1") == "1" else 0
    with db_cursor(commit=True) as cursor:
        if cartao_id:
            obter_cartao(usuario_id, cartao_id)
            cursor.execute(
                """
                UPDATE cartoes_credito SET nome=%s, bandeira=%s, limite_total=%s, dia_fechamento=%s,
                    dia_vencimento=%s, imagem_url=%s, ativo=%s
                WHERE id=%s AND usuario_id=%s
                """,
                (
                    nome,
                    bandeira,
                    limite_total,
                    dia_fechamento,
                    dia_vencimento,
                    imagem_url,
                    ativo,
                    cartao_id,
                    usuario_id,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO cartoes_credito (usuario_id, nome, bandeira, limite_total, dia_fechamento, dia_vencimento, imagem_url, ativo)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (usuario_id, nome, bandeira, limite_total, dia_fechamento, dia_vencimento, imagem_url, ativo),
            )


def obter_cartao(usuario_id, cartao_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM cartoes_credito WHERE id=%s AND usuario_id=%s", (cartao_id, usuario_id))
        cartao = cursor.fetchone()
    if not cartao:
        raise ValueError("Cartão não encontrado.")
    return cartao


def deletar_cartao(usuario_id, cartao_id):
    obter_cartao(usuario_id, cartao_id)
    with db_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM compras_cartao WHERE cartao_id=%s AND usuario_id=%s", (cartao_id, usuario_id))
        cursor.execute(
            "UPDATE movimentacoes SET cartao_id=NULL, referencia_id=NULL WHERE cartao_id=%s AND usuario_id=%s",
            (cartao_id, usuario_id),
        )
        cursor.execute("DELETE FROM cartoes_credito WHERE id=%s AND usuario_id=%s", (cartao_id, usuario_id))


def melhor_dia_compra(cartao):
    dia = int(cartao["dia_fechamento"] or 1) + 1
    return 1 if dia > 31 else dia


def proxima_data_dia(dia):
    hoje_ = hoje()
    data = data_por_dia(hoje_.strftime("%Y-%m"), dia)
    if data < hoje_:
        data = data_por_dia(somar_meses(hoje_.replace(day=1), 1).strftime("%Y-%m"), dia)
    return data


def alertas_cartoes(usuario_id):
    alertas = []
    for c in listar_cartoes(usuario_id, apenas_ativos=True):
        if 0 <= c["dias_para_fechamento"] <= 7:
            alertas.append(
                f"O cartão {c['nome']} fecha em {c['dias_para_fechamento']} dia(s). Melhor dia de compra: dia {c['melhor_dia_compra']}."
            )
        if 0 <= c["dias_para_vencimento"] <= 7:
            alertas.append(f"A fatura do cartão {c['nome']} vence em {c['dias_para_vencimento']} dia(s).")
    return alertas


def registrar_compra_cartao(usuario_id, form):
    cartao_id = int(form.get("cartao_id") or 0)
    obter_cartao(usuario_id, cartao_id)
    descricao = texto_obrigatorio(form.get("descricao"), "Descrição", 160)
    valor_total = decimal_brl(form.get("valor_total"), "Valor total")
    parcelas = inteiro(form.get("parcelas") or 1, "Parcelas", 1, 240)
    if valor_total * 100 < parcelas:
        raise ValueError("Cada parcela deve ter pelo menos um centavo.")
    valor_parcela = (valor_total / Decimal(parcelas)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    data_compra = parse_data(form.get("data_compra"), hoje())
    categoria_id = validar_categoria(usuario_id, form.get("categoria_id"), "despesa")
    observacao = texto_opcional(form.get("observacao"), 1000)
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO compras_cartao (usuario_id, cartao_id, descricao, valor_total, valor_parcela, parcelas, data_compra, categoria_id, observacao)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                usuario_id,
                cartao_id,
                descricao,
                valor_total,
                valor_parcela,
                parcelas,
                data_compra,
                categoria_id,
                observacao,
            ),
        )
        return cursor.lastrowid


def _mes_vencimento_primeira_parcela(data_compra: date, cartao) -> str:
    fechamento = data_por_dia(data_compra.strftime("%Y-%m"), int(cartao.get("dia_fechamento") or 1))
    base_mes = data_compra.replace(day=1)
    if data_compra > fechamento:
        base_mes = somar_meses(base_mes, 1)
    # Quando o vencimento é antes/igual ao fechamento, a fatura normalmente vence no mês seguinte.
    if int(cartao.get("dia_vencimento") or 10) <= int(cartao.get("dia_fechamento") or 1):
        base_mes = somar_meses(base_mes, 1)
    return base_mes.strftime("%Y-%m")


def data_vencimento_fatura(cartao, ano_mes: str) -> date:
    return data_por_dia(normalizar_mes(ano_mes), int(cartao.get("dia_vencimento") or 10))


def parcelas_cartao_mes(usuario_id, ano_mes, cartao_id=None):
    ano_mes = normalizar_mes(ano_mes)
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT cc.*, ca.nome AS cartao_nome, ca.dia_fechamento, ca.dia_vencimento, cat.nome AS categoria_nome
            FROM compras_cartao cc
            JOIN cartoes_credito ca ON ca.id=cc.cartao_id
            LEFT JOIN categorias cat ON cat.id=cc.categoria_id
            WHERE cc.usuario_id=%s AND (%s IS NULL OR cc.cartao_id=%s)
            """,
            (usuario_id, cartao_id, cartao_id),
        )
        compras = cursor.fetchall()
    parcelas = []
    alvo = datetime.strptime(ano_mes + "-01", "%Y-%m-%d").date()
    for compra in compras:
        primeira = datetime.strptime(
            _mes_vencimento_primeira_parcela(compra["data_compra"], compra) + "-01", "%Y-%m-%d"
        ).date()
        diff = (alvo.year - primeira.year) * 12 + (alvo.month - primeira.month)
        if 0 <= diff < int(compra["parcelas"]):
            parcela_atual = diff + 1
            valor_parcela = Decimal(compra["valor_parcela"])
            if parcela_atual == int(compra["parcelas"]):
                valor_parcela = Decimal(compra["valor_total"]) - (
                    Decimal(compra["valor_parcela"]) * Decimal(int(compra["parcelas"]) - 1)
                )
            parcelas.append(
                {
                    "id": compra["id"],
                    "descricao": compra["descricao"],
                    "cartao_id": compra["cartao_id"],
                    "cartao_nome": compra["cartao_nome"],
                    "categoria_id": compra.get("categoria_id"),
                    "categoria_nome": compra.get("categoria_nome"),
                    "valor": valor_parcela,
                    "valor_total": Decimal(compra["valor_total"]),
                    "parcela_atual": parcela_atual,
                    "parcelas": compra["parcelas"],
                    "data_compra": compra["data_compra"],
                    "vencimento": data_vencimento_fatura(compra, ano_mes),
                }
            )
    parcelas.sort(key=lambda p: (p["cartao_nome"], p["vencimento"], p["descricao"]))
    return parcelas


def total_fatura_cartao_mes(usuario_id, cartao_id, ano_mes):
    return sum((Decimal(p["valor"] or 0) for p in parcelas_cartao_mes(usuario_id, ano_mes, cartao_id)), Decimal("0.00"))


def meses_a_partir(ano_mes, quantidade=4):
    base = datetime.strptime(normalizar_mes(ano_mes) + "-01", "%Y-%m-%d").date()
    return [somar_meses(base, i).strftime("%Y-%m") for i in range(quantidade)]


def listar_compras_cartao(usuario_id, cartao_id=None, limite=200):
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT cc.*, ca.nome AS cartao_nome, cat.nome AS categoria_nome
            FROM compras_cartao cc
            JOIN cartoes_credito ca ON ca.id=cc.cartao_id
            LEFT JOIN categorias cat ON cat.id=cc.categoria_id
            WHERE cc.usuario_id=%s AND (%s IS NULL OR cc.cartao_id=%s)
            ORDER BY cc.data_compra DESC, cc.id DESC
            LIMIT %s
            """,
            (usuario_id, cartao_id, cartao_id, int(limite)),
        )
        return cursor.fetchall()


def compromisso_cartao(usuario_id, ano_mes, cartao_id=None):
    """Outstanding scheduled installments, assuming earlier invoices were settled."""
    target = datetime.strptime(normalizar_mes(ano_mes) + "-01", "%Y-%m-%d").date()
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT cc.*, ca.dia_fechamento, ca.dia_vencimento FROM compras_cartao cc "
            "JOIN cartoes_credito ca ON ca.id=cc.cartao_id "
            "WHERE cc.usuario_id=%s AND (%s IS NULL OR cc.cartao_id=%s)",
            (usuario_id, cartao_id, cartao_id),
        )
        purchases = cursor.fetchall()
    total = Decimal("0.00")
    for purchase in purchases:
        first = datetime.strptime(
            _mes_vencimento_primeira_parcela(purchase["data_compra"], purchase) + "-01", "%Y-%m-%d"
        ).date()
        elapsed = max(0, (target.year - first.year) * 12 + target.month - first.month)
        if elapsed < purchase["parcelas"]:
            total += purchase["valor_total"] - purchase["valor_parcela"] * elapsed
    return total


def listar_cartoes(usuario_id, apenas_ativos=False, ano_mes=None):
    ano_mes = normalizar_mes(ano_mes or mes_atual())
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM cartoes_credito WHERE usuario_id=%s AND (%s=0 OR ativo=1) ORDER BY ativo DESC, nome",
            (usuario_id, int(apenas_ativos)),
        )
        cartoes = cursor.fetchall()
    proximos_meses = meses_a_partir(ano_mes, 4)
    for cartao in cartoes:
        cartao["melhor_dia_compra"] = melhor_dia_compra(cartao)
        cartao["proxima_data_fechamento"] = proxima_data_dia(cartao["dia_fechamento"])
        cartao["proxima_data_vencimento"] = proxima_data_dia(cartao["dia_vencimento"])
        cartao["dias_para_fechamento"] = (cartao["proxima_data_fechamento"] - hoje()).days
        cartao["dias_para_vencimento"] = (cartao["proxima_data_vencimento"] - hoje()).days
        faturas = []
        for mes_ref in proximos_meses:
            total = total_fatura_cartao_mes(usuario_id, cartao["id"], mes_ref)
            faturas.append({"ano_mes": mes_ref, "total": total, "vencimento": data_vencimento_fatura(cartao, mes_ref)})
        cartao["faturas"] = faturas
        cartao["fatura_atual"] = faturas[0]["total"] if faturas else Decimal("0.00")
        cartao["proximas_faturas"] = faturas[1:]
        cartao["limite_disponivel_estimado"] = max(
            Decimal("0.00"),
            Decimal(cartao["limite_total"] or 0) - compromisso_cartao(usuario_id, ano_mes, cartao["id"]),
        )
    return cartoes


def resumo_faturas_geral(usuario_id, ano_mes, meses=4):
    # Inactive cards can still have installments due.
    cartoes = listar_cartoes(usuario_id, ano_mes=ano_mes)
    resultado = []
    for mes_ref in meses_a_partir(ano_mes, meses):
        total = Decimal("0.00")
        por_cartao = []
        for cartao in cartoes:
            valor = total_fatura_cartao_mes(usuario_id, cartao["id"], mes_ref)
            total += valor
            por_cartao.append({"cartao_id": cartao["id"], "cartao_nome": cartao["nome"], "total": valor})
        resultado.append({"ano_mes": mes_ref, "total": total, "por_cartao": por_cartao})
    return resultado


def deletar_compra_cartao(usuario_id, compra_id):
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "DELETE FROM movimentacoes WHERE usuario_id=%s AND origem='cartao' AND referencia_id=%s",
            (usuario_id, compra_id),
        )
        cursor.execute("DELETE FROM compras_cartao WHERE id=%s AND usuario_id=%s", (compra_id, usuario_id))
        if cursor.rowcount == 0:
            raise ValueError("Compra não encontrada.")
