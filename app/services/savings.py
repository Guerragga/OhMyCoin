from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from database import db_cursor
from .common import decimal_brl, hoje, parse_data, somar_meses, texto_obrigatorio, texto_opcional


def salvar_caixinha(usuario_id, form, caixinha_id=None):
    nome = texto_obrigatorio(form.get("nome"), "Nome", 120)
    valor_guardado = decimal_brl(form.get("valor_guardado") or 0, "Valor guardado", permite_zero=True)
    meta = decimal_brl(form.get("meta"), "Meta") if form.get("meta") else None
    aporte_mensal = decimal_brl(form.get("aporte_mensal") or 0, "Aporte mensal", permite_zero=True)
    data_inicio = parse_data(form.get("data_inicio"), hoje())
    descricao = texto_opcional(form.get("descricao"), 2000)
    with db_cursor(commit=True) as cursor:
        if caixinha_id:
            obter_caixinha(usuario_id, caixinha_id)
            cursor.execute(
                """
                UPDATE caixinhas SET nome=%s, valor_guardado=%s, meta=%s, aporte_mensal=%s, data_inicio=%s, descricao=%s
                WHERE id=%s AND usuario_id=%s
                """,
                (nome, valor_guardado, meta, aporte_mensal, data_inicio, descricao, caixinha_id, usuario_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO caixinhas (usuario_id, nome, valor_guardado, meta, aporte_mensal, data_inicio, descricao)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (usuario_id, nome, valor_guardado, meta, aporte_mensal, data_inicio, descricao),
            )


def obter_caixinha(usuario_id, caixinha_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM caixinhas WHERE id=%s AND usuario_id=%s", (caixinha_id, usuario_id))
        caixinha = cursor.fetchone()
    if not caixinha:
        raise ValueError("Caixinha não encontrada.")
    return caixinha


def listar_caixinhas(usuario_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM caixinhas WHERE usuario_id=%s ORDER BY nome", (usuario_id,))
        caixinhas = cursor.fetchall()
    for item in caixinhas:
        meta = Decimal(item.get("meta") or 0)
        guardado = Decimal(item.get("valor_guardado") or 0)
        aporte = Decimal(item.get("aporte_mensal") or 0)
        item["progresso"] = None
        item["meses_restantes"] = None
        item["data_prevista"] = None
        if meta > 0:
            item["progresso"] = min(100, round(float((guardado / meta) * 100), 1))
            restante = meta - guardado
            if restante <= 0:
                item["meses_restantes"] = 0
                item["data_prevista"] = hoje()
            elif aporte > 0:
                meses = int((restante / aporte).to_integral_value(rounding=ROUND_HALF_UP))
                if aporte * meses < restante:
                    meses += 1
                item["meses_restantes"] = meses
                if meses <= (9998 - hoje().year) * 12:
                    item["data_prevista"] = somar_meses(hoje(), meses)
    return caixinhas


def movimentar_caixinha(usuario_id, caixinha_id, valor, acao):
    acao = (acao or "").strip().lower()
    if acao not in {"adicionar", "retirar"}:
        raise ValueError("Ação inválida para a caixinha.")

    valor = decimal_brl(valor, "Valor")
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "SELECT valor_guardado FROM caixinhas WHERE id=%s AND usuario_id=%s FOR UPDATE", (caixinha_id, usuario_id)
        )
        caixinha = cursor.fetchone()
        if not caixinha:
            raise ValueError("Caixinha não encontrada.")
        atual = Decimal(caixinha["valor_guardado"])
        novo = atual - valor if acao == "retirar" else atual + valor
        if novo < 0:
            raise ValueError("A caixinha não tem saldo suficiente.")
        novo = decimal_brl(novo, "Saldo", permite_zero=True)
        cursor.execute(
            "UPDATE caixinhas SET valor_guardado=%s WHERE id=%s AND usuario_id=%s", (novo, caixinha_id, usuario_id)
        )


def deletar_caixinha(usuario_id, caixinha_id):
    obter_caixinha(usuario_id, caixinha_id)
    with db_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM caixinhas WHERE id=%s AND usuario_id=%s", (caixinha_id, usuario_id))
