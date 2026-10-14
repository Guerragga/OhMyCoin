from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_DOWN

from database import db_cursor
from .accounts import validar_conta
from .cards import listar_compras_cartao, obter_cartao
from .categories import validar_categoria
from .common import (
    FORMAS_PAGAMENTO,
    TIPOS_MOVIMENTACAO,
    decimal_brl,
    hoje,
    inicio_fim_mes,
    inteiro,
    mes_atual,
    parse_data,
    texto_obrigatorio,
    texto_opcional,
)


def salvar_movimentacao(usuario_id, form, movimentacao_id=None):
    tipo = (form.get("tipo") or "").strip().lower()
    if tipo not in TIPOS_MOVIMENTACAO:
        raise ValueError("Tipo inválido.")
    valor = decimal_brl(form.get("valor"), "Valor")
    descricao = texto_obrigatorio(form.get("descricao"), "Descrição", 160)
    data_movimentacao = parse_data(form.get("data_movimentacao"), hoje())
    categoria_id = validar_categoria(usuario_id, form.get("categoria_id"), tipo)
    forma_pagamento = (form.get("forma_pagamento") or "conta").strip().lower()
    if forma_pagamento not in FORMAS_PAGAMENTO:
        forma_pagamento = "conta"
    if tipo == "receita":
        forma_pagamento = "conta"
    conta_id = None
    cartao_id = None
    parcelas = 1
    if forma_pagamento == "cartao":
        if tipo != "despesa":
            raise ValueError("Cartão de crédito só pode ser usado em saídas.")
        cartao_id = int(form.get("cartao_id") or 0)
        obter_cartao(usuario_id, cartao_id)
        parcelas = inteiro(form.get("parcelas") or 1, "Parcelas", 1, 240)
        if valor * 100 < parcelas:
            raise ValueError("Cada parcela deve ter pelo menos um centavo.")
    else:
        conta_id = validar_conta(usuario_id, form.get("conta_id"))
    observacao = texto_opcional(form.get("observacao"), 2000)

    with db_cursor(commit=True) as cursor:
        compra_id = None
        origem = "manual"
        if movimentacao_id:
            antiga = obter_movimentacao(usuario_id, movimentacao_id)
            if antiga.get("origem") == "divida":
                raise ValueError("Estorne o pagamento e registre novamente para corrigir uma parcela de dívida.")
            if antiga.get("origem") == "cartao" and antiga.get("referencia_id"):
                if forma_pagamento == "cartao":
                    valor_parcela = (valor / Decimal(parcelas)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
                    cursor.execute(
                        """
                        UPDATE compras_cartao
                        SET cartao_id=%s, descricao=%s, valor_total=%s, valor_parcela=%s, parcelas=%s,
                            data_compra=%s, categoria_id=%s, observacao=%s
                        WHERE id=%s AND usuario_id=%s
                        """,
                        (
                            cartao_id,
                            descricao,
                            valor,
                            valor_parcela,
                            parcelas,
                            data_movimentacao,
                            categoria_id,
                            observacao,
                            antiga["referencia_id"],
                            usuario_id,
                        ),
                    )
                    compra_id = antiga["referencia_id"]
                    origem = "cartao"
                else:
                    cursor.execute(
                        "DELETE FROM compras_cartao WHERE id=%s AND usuario_id=%s",
                        (antiga["referencia_id"], usuario_id),
                    )
            elif forma_pagamento == "cartao":
                valor_parcela = (valor / Decimal(parcelas)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
                cursor.execute(
                    """
                    INSERT INTO compras_cartao (usuario_id, cartao_id, descricao, valor_total, valor_parcela, parcelas, data_compra, categoria_id, observacao)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        usuario_id,
                        cartao_id,
                        descricao,
                        valor,
                        valor_parcela,
                        parcelas,
                        data_movimentacao,
                        categoria_id,
                        observacao,
                    ),
                )
                compra_id = cursor.lastrowid
                origem = "cartao"
            cursor.execute(
                """
                UPDATE movimentacoes SET tipo=%s, valor=%s, descricao=%s, data_movimentacao=%s,
                    categoria_id=%s, conta_id=%s, forma_pagamento=%s, cartao_id=%s, parcelas=%s,
                    origem=%s, referencia_id=%s, observacao=%s
                WHERE id=%s AND usuario_id=%s
                """,
                (
                    tipo,
                    valor,
                    descricao,
                    data_movimentacao,
                    categoria_id,
                    conta_id,
                    forma_pagamento,
                    cartao_id,
                    parcelas,
                    origem,
                    compra_id,
                    observacao,
                    movimentacao_id,
                    usuario_id,
                ),
            )
        else:
            if forma_pagamento == "cartao":
                valor_parcela = (valor / Decimal(parcelas)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
                cursor.execute(
                    """
                    INSERT INTO compras_cartao (usuario_id, cartao_id, descricao, valor_total, valor_parcela, parcelas, data_compra, categoria_id, observacao)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        usuario_id,
                        cartao_id,
                        descricao,
                        valor,
                        valor_parcela,
                        parcelas,
                        data_movimentacao,
                        categoria_id,
                        observacao,
                    ),
                )
                compra_id = cursor.lastrowid
                origem = "cartao"
            cursor.execute(
                """
                INSERT INTO movimentacoes (usuario_id, tipo, valor, descricao, data_movimentacao, categoria_id, conta_id,
                                           forma_pagamento, cartao_id, parcelas, origem, referencia_id, observacao)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    usuario_id,
                    tipo,
                    valor,
                    descricao,
                    data_movimentacao,
                    categoria_id,
                    conta_id,
                    forma_pagamento,
                    cartao_id,
                    parcelas,
                    origem,
                    compra_id,
                    observacao,
                ),
            )


def obter_movimentacao(usuario_id, movimentacao_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM movimentacoes WHERE id=%s AND usuario_id=%s", (movimentacao_id, usuario_id))
        mov = cursor.fetchone()
    if not mov:
        raise ValueError("Movimentação não encontrada.")
    return mov


def deletar_movimentacao(usuario_id, movimentacao_id):
    mov = obter_movimentacao(usuario_id, movimentacao_id)
    with db_cursor(commit=True) as cursor:
        if mov.get("origem") == "divida":
            # Lock the debt before the payment, the same order used when paying.
            cursor.execute(
                "SELECT id FROM dividas WHERE id=%s AND usuario_id=%s FOR UPDATE",
                (mov.get("referencia_id"), usuario_id),
            )
            debt = cursor.fetchone()
            cursor.execute(
                "SELECT id FROM pagamentos_dividas WHERE movimentacao_id=%s AND usuario_id=%s FOR UPDATE",
                (movimentacao_id, usuario_id),
            )
            payment = cursor.fetchone()
            if debt and payment:
                cursor.execute(
                    "DELETE FROM pagamentos_dividas WHERE id=%s AND usuario_id=%s", (payment["id"], usuario_id)
                )
                cursor.execute(
                    "UPDATE dividas SET parcelas_pagas=GREATEST(0, parcelas_pagas-1), "
                    "saldo_devedor=LEAST(valor_total, saldo_devedor+valor_parcela), "
                    "ativa=IF(status='quitada',1,ativa), status=IF(status='quitada','ativa',status) "
                    "WHERE id=%s AND usuario_id=%s",
                    (debt["id"], usuario_id),
                )
        if mov.get("origem") == "cartao" and mov.get("referencia_id"):
            cursor.execute(
                "DELETE FROM compras_cartao WHERE id=%s AND usuario_id=%s", (mov["referencia_id"], usuario_id)
            )
        cursor.execute("DELETE FROM movimentacoes WHERE id=%s AND usuario_id=%s", (movimentacao_id, usuario_id))


def filtros_movimentacoes_from_args(args, mes_padrao=None):
    filtros = {}
    mes = (args.get("mes") or mes_padrao or mes_atual()).strip()[:7]
    data_inicio = args.get("data_inicio")
    data_fim = args.get("data_fim")
    if data_inicio or data_fim:
        if data_inicio:
            filtros["inicio"] = parse_data(data_inicio)
        if data_fim:
            filtros["fim_inclusive"] = parse_data(data_fim)
    else:
        _, inicio, fim = inicio_fim_mes(mes)
        filtros.update({"inicio": inicio, "fim": fim})
    for chave in ("tipo", "forma_pagamento", "origem"):
        valor = (args.get(chave) or "").strip().lower()
        if valor:
            filtros[chave] = valor
    for chave in ("categoria_id", "conta_id", "cartao_id"):
        valor = args.get(chave)
        if valor:
            filtros[chave] = int(valor)
    filtros["mes"] = mes
    return filtros


def _aplicar_filtros_item(item, filtros):
    if filtros.get("tipo") and item.get("tipo") != filtros["tipo"]:
        return False
    if filtros.get("forma_pagamento") and item.get("forma_pagamento") != filtros["forma_pagamento"]:
        return False
    if filtros.get("origem") and item.get("origem") != filtros["origem"]:
        return False
    if filtros.get("categoria_id") and item.get("categoria_id") != filtros["categoria_id"]:
        return False
    if filtros.get("conta_id") and item.get("conta_id") != filtros["conta_id"]:
        return False
    if filtros.get("cartao_id") and item.get("cartao_id") != filtros["cartao_id"]:
        return False
    data_item = item.get("data_movimentacao")
    if filtros.get("inicio") and data_item < filtros["inicio"]:
        return False
    if filtros.get("fim") and data_item >= filtros["fim"]:
        return False
    if filtros.get("fim_inclusive") and data_item > filtros["fim_inclusive"]:
        return False
    return True


def listar_movimentacoes_reais(usuario_id, filtros=None, limite=500):
    filtros = filtros or {}
    params = [usuario_id]
    for key in (
        "inicio",
        "fim",
        "fim_inclusive",
        "tipo",
        "forma_pagamento",
        "origem",
        "categoria_id",
        "conta_id",
        "cartao_id",
    ):
        value = filtros.get(key) or None
        params.extend((value, value))
    sql = """
        SELECT m.*, c.nome AS categoria_nome, ct.nome AS conta_nome, ca.nome AS cartao_nome
        FROM movimentacoes m
        LEFT JOIN categorias c ON c.id=m.categoria_id
        LEFT JOIN contas ct ON ct.id=m.conta_id
        LEFT JOIN cartoes_credito ca ON ca.id=m.cartao_id
        WHERE m.usuario_id=%s
          AND (%s IS NULL OR m.data_movimentacao >=%s)
          AND (%s IS NULL OR m.data_movimentacao <%s)
          AND (%s IS NULL OR m.data_movimentacao <=%s)
          AND (%s IS NULL OR m.tipo=%s)
          AND (%s IS NULL OR m.forma_pagamento=%s)
          AND (%s IS NULL OR m.origem=%s)
          AND (%s IS NULL OR m.categoria_id=%s)
          AND (%s IS NULL OR m.conta_id=%s)
          AND (%s IS NULL OR m.cartao_id=%s)
        ORDER BY m.data_movimentacao DESC, m.id DESC
        LIMIT %s
    """
    params.append(limite)
    with db_cursor() as cursor:
        cursor.execute(sql, tuple(params))
        itens = cursor.fetchall()
    for item in itens:
        item["sintetica"] = False
        item["entidade"] = "movimentacao"
    return itens


def listar_movimentacoes(usuario_id, filtros=None):
    """Lista unificada para tela de Movimentações.

    Evita o erro clássico do sistema: compra de cartão lançada direto em
    compras_cartao não aparecia em Movimentações; compra de cartão lançada via
    Movimentações podia aparecer duplicada. Aqui a compra do cartão aparece uma
    única vez, como movimento sintético do cartão.
    """
    filtros = filtros or {}
    base_filters = dict(filtros)
    itens = [
        item
        for item in listar_movimentacoes_reais(usuario_id, base_filters, limite=800)
        if not (item.get("origem") == "cartao" and item.get("referencia_id"))
    ]

    # Compras de cartão entram como movimentações sintéticas pela data da compra.
    if not filtros.get("conta_id") and filtros.get("tipo") in (None, "", "despesa"):
        compras = listar_compras_cartao(usuario_id, cartao_id=filtros.get("cartao_id"), limite=1000)
        for compra in compras:
            item = {
                "id": compra["id"],
                "usuario_id": usuario_id,
                "tipo": "despesa",
                "valor": Decimal(compra["valor_total"] or 0),
                "descricao": compra["descricao"],
                "data_movimentacao": compra["data_compra"],
                "categoria_id": compra.get("categoria_id"),
                "categoria_nome": compra.get("categoria_nome"),
                "conta_id": None,
                "conta_nome": None,
                "cartao_id": compra.get("cartao_id"),
                "cartao_nome": compra.get("cartao_nome"),
                "forma_pagamento": "cartao",
                "parcelas": compra.get("parcelas") or 1,
                "origem": "cartao",
                "referencia_id": compra["id"],
                "observacao": compra.get("observacao"),
                "sintetica": True,
                "entidade": "compra_cartao",
            }
            if _aplicar_filtros_item(item, filtros):
                itens.append(item)

    itens.sort(key=lambda x: (x.get("data_movimentacao") or date.min, x.get("id") or 0), reverse=True)
    return itens[:500]


def listar_movimentacoes_conta(usuario_id, conta_id, filtros=None):
    filtros = dict(filtros or {})
    filtros["conta_id"] = int(conta_id)
    return listar_movimentacoes_reais(usuario_id, filtros, limite=1000)
