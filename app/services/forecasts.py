from __future__ import annotations

from database import db_cursor
from .accounts import validar_conta
from .categories import validar_categoria
from .common import (
    TIPOS_MOVIMENTACAO,
    decimal_brl,
    inteiro,
    normalizar_mes,
    texto_obrigatorio,
    texto_opcional,
)


def salvar_previsao(usuario_id, form, previsao_id=None):
    ano_mes = normalizar_mes(form.get("ano_mes"))
    tipo = (form.get("tipo") or "").strip().lower()
    if tipo not in TIPOS_MOVIMENTACAO:
        raise ValueError("Tipo inválido.")
    descricao = texto_obrigatorio(form.get("descricao"), "Descrição", 160)
    valor_previsto = decimal_brl(form.get("valor_previsto"), "Valor previsto")
    dia_previsto = inteiro(form.get("dia_previsto") or 1, "Dia previsto", 1, 31)
    categoria_id = validar_categoria(usuario_id, form.get("categoria_id"), tipo)
    conta_id = validar_conta(usuario_id, form.get("conta_id"))
    recorrente = 1 if form.get("recorrente") == "1" else 0
    observacao = texto_opcional(form.get("observacao"), 1000)
    with db_cursor(commit=True) as cursor:
        if previsao_id:
            obter_previsao(usuario_id, previsao_id)
            cursor.execute(
                """
                UPDATE previsoes_mensais SET ano_mes=%s, tipo=%s, descricao=%s, valor_previsto=%s,
                    dia_previsto=%s, categoria_id=%s, conta_id=%s, recorrente=%s, observacao=%s
                WHERE id=%s AND usuario_id=%s
                """,
                (
                    ano_mes,
                    tipo,
                    descricao,
                    valor_previsto,
                    dia_previsto,
                    categoria_id,
                    conta_id,
                    recorrente,
                    observacao,
                    previsao_id,
                    usuario_id,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO previsoes_mensais (usuario_id, ano_mes, tipo, descricao, valor_previsto, dia_previsto, categoria_id, conta_id, recorrente, observacao)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    usuario_id,
                    ano_mes,
                    tipo,
                    descricao,
                    valor_previsto,
                    dia_previsto,
                    categoria_id,
                    conta_id,
                    recorrente,
                    observacao,
                ),
            )


def obter_previsao(usuario_id, previsao_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM previsoes_mensais WHERE id=%s AND usuario_id=%s", (previsao_id, usuario_id))
        previsao = cursor.fetchone()
    if not previsao:
        raise ValueError("Previsão não encontrada.")
    return previsao


def listar_previsoes(usuario_id, ano_mes):
    ano_mes = normalizar_mes(ano_mes)
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT p.*, c.nome AS categoria_nome, ct.nome AS conta_nome
            FROM previsoes_mensais p
            LEFT JOIN categorias c ON c.id=p.categoria_id
            LEFT JOIN contas ct ON ct.id=p.conta_id
            WHERE p.usuario_id=%s
              AND (p.ano_mes=%s OR (p.recorrente=1 AND p.ano_mes <= %s))
            ORDER BY p.tipo DESC, p.dia_previsto, p.descricao
            """,
            (usuario_id, ano_mes, ano_mes),
        )
        return cursor.fetchall()


def deletar_previsao(usuario_id, previsao_id):
    obter_previsao(usuario_id, previsao_id)
    with db_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM previsoes_mensais WHERE id=%s AND usuario_id=%s", (previsao_id, usuario_id))
