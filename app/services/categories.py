from __future__ import annotations

from database import db_cursor
from .common import TIPOS_CATEGORIA, texto_obrigatorio, texto_opcional


def listar_categorias(usuario_id, tipo=None):
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM categorias
            WHERE usuario_id=%s
              AND (%s IS NULL OR tipo IN (%s, 'geral'))
            ORDER BY tipo, nome
            """,
            (usuario_id, tipo, tipo),
        )
        return cursor.fetchall()


def obter_categoria(usuario_id, categoria_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM categorias WHERE id=%s AND usuario_id=%s", (categoria_id, usuario_id))
        categoria = cursor.fetchone()
    if not categoria:
        raise ValueError("Categoria não encontrada.")
    return categoria


def validar_categoria(usuario_id, categoria_id, tipo=None):
    if not categoria_id:
        return None
    categoria = obter_categoria(usuario_id, int(categoria_id))
    if tipo and categoria["tipo"] not in {tipo, "geral"}:
        raise ValueError(f"Categoria incompatível com {tipo}.")
    return categoria["id"]


def criar_categoria(usuario_id, nome, tipo, descricao=None):
    nome = texto_obrigatorio(nome, "Nome", 100)
    tipo = (tipo or "geral").strip().lower()
    if tipo not in TIPOS_CATEGORIA:
        raise ValueError("Tipo de categoria inválido.")
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "INSERT INTO categorias (usuario_id, nome, tipo, descricao) VALUES (%s,%s,%s,%s)",
            (usuario_id, nome, tipo, texto_opcional(descricao, 255)),
        )


def atualizar_categoria(usuario_id, categoria_id, nome, tipo, descricao=None):
    obter_categoria(usuario_id, categoria_id)
    nome = texto_obrigatorio(nome, "Nome", 100)
    tipo = (tipo or "geral").strip().lower()
    if tipo not in TIPOS_CATEGORIA:
        raise ValueError("Tipo de categoria inválido.")
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "UPDATE categorias SET nome=%s, tipo=%s, descricao=%s WHERE id=%s AND usuario_id=%s",
            (nome, tipo, texto_opcional(descricao, 255), categoria_id, usuario_id),
        )


def deletar_categoria(usuario_id, categoria_id):
    obter_categoria(usuario_id, categoria_id)
    with db_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM categorias WHERE id=%s AND usuario_id=%s", (categoria_id, usuario_id))
