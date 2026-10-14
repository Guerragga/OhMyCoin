from __future__ import annotations

from decimal import Decimal

from database import db_cursor
from .common import TIPOS_CONTA, decimal_brl, texto_obrigatorio, validar_url_imagem


def obter_conta(usuario_id, conta_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM contas WHERE id=%s AND usuario_id=%s", (conta_id, usuario_id))
        conta = cursor.fetchone()
    if not conta:
        raise ValueError("Conta não encontrada.")
    return conta


def validar_conta(usuario_id, conta_id):
    if not conta_id:
        return None
    return obter_conta(usuario_id, int(conta_id))["id"]


def salvar_conta(usuario_id, form, conta_id=None):
    nome = texto_obrigatorio(form.get("nome"), "Nome", 100)
    tipo = (form.get("tipo") or "corrente").strip().lower()
    if tipo not in TIPOS_CONTA:
        raise ValueError("Tipo de conta inválido.")
    saldo_inicial = decimal_brl(form.get("saldo_inicial") or "0", "Saldo inicial", permite_zero=True)
    moeda = (form.get("moeda") or "BRL").strip().upper()
    if moeda != "BRL":
        raise ValueError("A moeda suportada é BRL.")
    imagem_url = validar_url_imagem(form.get("imagem_url"))
    ativa = 1 if form.get("ativa", "1") == "1" else 0
    with db_cursor(commit=True) as cursor:
        if conta_id:
            obter_conta(usuario_id, conta_id)
            cursor.execute(
                """
                UPDATE contas SET nome=%s, tipo=%s, saldo_inicial=%s, moeda=%s, imagem_url=%s, ativa=%s
                WHERE id=%s AND usuario_id=%s
                """,
                (nome, tipo, saldo_inicial, moeda, imagem_url, ativa, conta_id, usuario_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO contas (usuario_id, nome, tipo, saldo_inicial, moeda, imagem_url, ativa)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (usuario_id, nome, tipo, saldo_inicial, moeda, imagem_url, ativa),
            )


def deletar_conta(usuario_id, conta_id):
    obter_conta(usuario_id, conta_id)
    with db_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM contas WHERE id=%s AND usuario_id=%s", (conta_id, usuario_id))


def saldo_conta(usuario_id, conta_id):
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT c.saldo_inicial,
                   COALESCE(SUM(CASE WHEN m.tipo='receita' THEN m.valor ELSE -m.valor END), 0) AS movimentos
            FROM contas c
            LEFT JOIN movimentacoes m ON m.conta_id = c.id AND m.usuario_id = c.usuario_id
            WHERE c.id=%s AND c.usuario_id=%s
            GROUP BY c.id, c.saldo_inicial
            """,
            (conta_id, usuario_id),
        )
        row = cursor.fetchone()
    if not row:
        return Decimal("0.00")
    return Decimal(row["saldo_inicial"] or 0) + Decimal(row["movimentos"] or 0)


def listar_contas(usuario_id, apenas_ativas=False):
    somente_ativas = 1 if apenas_ativas else 0
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM contas
            WHERE usuario_id=%s
              AND (%s=0 OR ativa=1)
            ORDER BY CASE WHEN tipo='carteira' THEN 0 ELSE 1 END, ativa DESC, nome
            """,
            (usuario_id, somente_ativas),
        )
        contas = cursor.fetchall()
    for conta in contas:
        conta["saldo_atual"] = saldo_conta(usuario_id, conta["id"])
    return contas
