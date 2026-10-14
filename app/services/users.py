from __future__ import annotations

import logging
from datetime import datetime, timedelta
import secrets

from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from database import db_cursor
from .common import (
    CHART_FLAGS,
    normalizar_tema,
    texto_obrigatorio,
    texto_opcional,
    validar_email,
    validar_emoji,
    validar_senha,
)

logger = logging.getLogger(__name__)
DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_urlsafe(32))


def registrar_auditoria(usuario_id, acao, entidade=None, entidade_id=None, detalhes=None, ip=None):
    try:
        with db_cursor(commit=True) as cursor:
            cursor.execute(
                """
                INSERT INTO audit_logs (usuario_id, acao, entidade, entidade_id, detalhes, ip)
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (
                    usuario_id,
                    texto_obrigatorio(acao, "Ação", 80),
                    texto_opcional(entidade, 80),
                    entidade_id,
                    texto_opcional(detalhes, 1000),
                    texto_opcional(ip, 45),
                ),
            )
    except Exception:
        # Auditoria não deve derrubar a operação principal, mas a falha precisa ser observável.
        logger.error("Falha ao registrar evento de auditoria")


def verificar_rate_limit_login(email, ip):
    agora = datetime.now()
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT tentativas, bloqueado_ate FROM login_attempts WHERE email=%s AND ip=%s",
            (email, ip),
        )
        row = cursor.fetchone()
        window = agora - timedelta(minutes=Config.LOGIN_WINDOW_MINUTES)
        cursor.execute(
            "SELECT COALESCE(SUM(tentativas),0) AS total FROM login_attempts WHERE email=%s AND ultima_tentativa >= %s",
            (email, window),
        )
        account_total = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT COALESCE(SUM(tentativas),0) AS total FROM login_attempts WHERE ip=%s AND ultima_tentativa >= %s",
            (ip, window),
        )
        ip_total = cursor.fetchone()["total"]
    if account_total >= Config.LOGIN_MAX_ATTEMPTS or ip_total >= Config.LOGIN_MAX_ATTEMPTS * 5:
        raise ValueError("Muitas tentativas de login. Aguarde antes de tentar novamente.")
    if row and row.get("bloqueado_ate") and row["bloqueado_ate"] > agora:
        minutos = max(1, int((row["bloqueado_ate"] - agora).total_seconds() // 60) + 1)
        raise ValueError(f"Muitas tentativas de login. Tente novamente em {minutos} minuto(s).")


def registrar_login_falha(email, ip):
    agora = datetime.now()
    bloqueado_ate = None
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "INSERT IGNORE INTO login_attempts (email, ip, tentativas, primeira_tentativa, ultima_tentativa) VALUES (%s,%s,0,%s,%s)",
            (email, ip, agora, agora),
        )
        cursor.execute(
            "SELECT tentativas, primeira_tentativa FROM login_attempts WHERE email=%s AND ip=%s FOR UPDATE",
            (email, ip),
        )
        row = cursor.fetchone()
        if not row or (agora - row["primeira_tentativa"]).total_seconds() > Config.LOGIN_WINDOW_MINUTES * 60:
            tentativas = 1
            primeira = agora
        else:
            tentativas = int(row["tentativas"] or 0) + 1
            primeira = row["primeira_tentativa"]
        if tentativas >= Config.LOGIN_MAX_ATTEMPTS:
            bloqueado_ate = agora + timedelta(minutes=Config.LOGIN_LOCKOUT_MINUTES)
        cursor.execute(
            """
            INSERT INTO login_attempts (email, ip, tentativas, primeira_tentativa, ultima_tentativa, bloqueado_ate)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE tentativas=VALUES(tentativas), primeira_tentativa=VALUES(primeira_tentativa),
                ultima_tentativa=VALUES(ultima_tentativa), bloqueado_ate=VALUES(bloqueado_ate)
            """,
            (email, ip, tentativas, primeira, agora, bloqueado_ate),
        )


def limpar_login_falhas(email, ip):
    with db_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM login_attempts WHERE email=%s AND ip=%s", (email, ip))


def obter_usuario_por_email(email):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM usuarios WHERE email = %s AND ativo = 1", (email,))
        return cursor.fetchone()


def obter_usuario_por_id(usuario_id):
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, nome, email, senha, nivel_acesso, ativo, criado_em, avatar_emoji, tema,
                   mostrar_grafico_real_previsto, mostrar_grafico_categorias, mostrar_grafico_evolucao,
                   mostrar_grafico_forma_pagamento, mostrar_grafico_contas, mostrar_grafico_cartoes
            FROM usuarios WHERE id = %s
            """,
            (usuario_id,),
        )
        return cursor.fetchone()


def usuario_e_admin(usuario_id):
    usuario = obter_usuario_por_id(usuario_id)
    return bool(usuario and usuario.get("nivel_acesso") == "ADMIN" and usuario.get("ativo"))


def senha_confere(hash_armazenado, senha_digitada):
    if not senha_digitada:
        return False
    hash_armazenado = hash_armazenado or DUMMY_PASSWORD_HASH
    try:
        return check_password_hash(hash_armazenado, senha_digitada)
    except (ValueError, TypeError):
        return False


def criar_usuario(nome, email, senha, *, nivel_acesso="USER"):
    # Public registration never accepts a caller-supplied role.
    if nivel_acesso not in {"USER", "ADMIN"}:
        raise ValueError("Nível de acesso inválido.")
    nome = texto_obrigatorio(nome, "Nome", 100)
    email = validar_email(email)
    senha = validar_senha(senha)
    senha_hash = generate_password_hash(senha)

    with db_cursor(commit=True) as cursor:
        cursor.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
        if cursor.fetchone():
            raise ValueError("Este e-mail já está cadastrado.")

        cursor.execute(
            "INSERT INTO usuarios (nome, email, senha, nivel_acesso) VALUES (%s, %s, %s, %s)",
            (nome, email, senha_hash, nivel_acesso),
        )
        usuario_id = cursor.lastrowid
        criar_estrutura_padrao_usuario(usuario_id, cursor)
        return usuario_id


def criar_estrutura_padrao_usuario(usuario_id, cursor=None):
    categorias = [
        ("Salário", "receita", "Renda principal"),
        ("Freelancer", "receita", "Projetos e trabalhos extras"),
        ("Alimentação", "despesa", "Mercado e alimentação"),
        ("Transporte", "despesa", "Aplicativos, combustível e transporte público"),
        ("Moradia", "despesa", "Aluguel, energia, água e internet"),
        ("Dívidas", "despesa", "Parcelas fixas e financiamentos"),
        ("Jogos", "despesa", "Jogos, assinaturas e entretenimento"),
        ("Férias", "despesa", "Viagens, passeios e hospedagem"),
        ("Saúde", "despesa", "Consultas, farmácia e plano"),
        ("Lazer", "despesa", "Entretenimento geral"),
    ]

    def executar(cur):
        cur.execute(
            """
            INSERT IGNORE INTO contas (usuario_id, nome, tipo, saldo_inicial, moeda, ativa)
            VALUES (%s, 'Conta principal', 'corrente', 0.00, 'BRL', 1)
            """,
            (usuario_id,),
        )
        cur.execute(
            """
            INSERT IGNORE INTO contas (usuario_id, nome, tipo, saldo_inicial, moeda, ativa)
            VALUES (%s, 'Carteira', 'carteira', 0.00, 'BRL', 1)
            """,
            (usuario_id,),
        )
        for nome, tipo, descricao in categorias:
            cur.execute(
                """
                INSERT IGNORE INTO categorias (nome, tipo, descricao, usuario_id)
                VALUES (%s, %s, %s, %s)
                """,
                (nome, tipo, descricao, usuario_id),
            )

    if cursor:
        executar(cursor)
    else:
        with db_cursor(commit=True) as cur:
            executar(cur)


def configuracoes_usuario(usuario_id):
    usuario = obter_usuario_por_id(usuario_id)
    if not usuario:
        raise ValueError("Usuário não encontrado.")
    return {
        "avatar_emoji": usuario.get("avatar_emoji") or "💰",
        "tema": normalizar_tema(usuario.get("tema")),
        **{flag: bool(usuario.get(flag, 1)) for flag in CHART_FLAGS},
    }


def atualizar_perfil(usuario_id, form):
    nome = texto_obrigatorio(form.get("nome"), "Nome", 100)
    avatar = validar_emoji(form.get("avatar_emoji"))
    with db_cursor(commit=True) as cursor:
        cursor.execute("UPDATE usuarios SET nome=%s, avatar_emoji=%s WHERE id=%s", (nome, avatar, usuario_id))
    return nome, avatar


def alterar_senha_perfil(usuario_id, form):
    atual = form.get("senha_atual") or ""
    nova = validar_senha(form.get("nova_senha"))
    confirmar = form.get("confirmar_senha") or ""
    if nova != confirmar:
        raise ValueError("A confirmação da nova senha não confere.")
    usuario = obter_usuario_por_id(usuario_id)
    if not usuario or not senha_confere(usuario.get("senha"), atual):
        raise ValueError("Senha atual incorreta.")
    with db_cursor(commit=True) as cursor:
        cursor.execute("UPDATE usuarios SET senha=%s WHERE id=%s", (generate_password_hash(nova), usuario_id))
    registrar_auditoria(usuario_id, "senha_alterada", "usuarios", usuario_id)


def atualizar_configuracoes(usuario_id, form):
    tema = normalizar_tema(form.get("tema"))
    valores = {flag: 1 if form.get(flag) == "1" else 0 for flag in CHART_FLAGS}
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            UPDATE usuarios SET tema=%s,
                mostrar_grafico_real_previsto=%s, mostrar_grafico_categorias=%s,
                mostrar_grafico_evolucao=%s, mostrar_grafico_forma_pagamento=%s,
                mostrar_grafico_contas=%s, mostrar_grafico_cartoes=%s
            WHERE id=%s
            """,
            (tema, *[valores[flag] for flag in CHART_FLAGS], usuario_id),
        )
    return tema


def listar_usuarios_admin():
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, nome, email, nivel_acesso, ativo, avatar_emoji, tema, criado_em
            FROM usuarios
            ORDER BY ativo DESC, nome
            """
        )
        return cursor.fetchall()


def atualizar_usuario_admin(admin_id, usuario_id, form):
    if not usuario_e_admin(admin_id):
        raise ValueError("Acesso restrito a administradores.")
    usuario = obter_usuario_por_id(usuario_id)
    if not usuario:
        raise ValueError("Usuário não encontrado.")
    nome = texto_obrigatorio(form.get("nome"), "Nome", 100)
    email = validar_email(form.get("email"))
    nivel = (form.get("nivel_acesso") or "USER").strip().upper()
    if nivel not in {"USER", "ADMIN"}:
        raise ValueError("Nível inválido.")
    ativo = 1 if form.get("ativo") == "1" else 0
    if usuario_id == admin_id:
        ativo = 1
        nivel = "ADMIN"
    senha = (form.get("nova_senha") or "").strip()
    with db_cursor(commit=True) as cursor:
        cursor.execute("SELECT id FROM usuarios WHERE email=%s AND id<>%s", (email, usuario_id))
        if cursor.fetchone():
            raise ValueError("Este e-mail já está em uso por outro usuário.")
        if senha:
            validar_senha(senha)
            cursor.execute(
                "UPDATE usuarios SET nome=%s, email=%s, nivel_acesso=%s, ativo=%s, senha=%s WHERE id=%s",
                (nome, email, nivel, ativo, generate_password_hash(senha), usuario_id),
            )
        else:
            cursor.execute(
                "UPDATE usuarios SET nome=%s, email=%s, nivel_acesso=%s, ativo=%s WHERE id=%s",
                (nome, email, nivel, ativo, usuario_id),
            )
    registrar_auditoria(admin_id, "admin_atualizou_usuario", "usuarios", usuario_id, f"nivel={nivel}; ativo={ativo}")


def deletar_usuario_admin(admin_id, usuario_id):
    if not usuario_e_admin(admin_id):
        raise ValueError("Acesso restrito a administradores.")
    if usuario_id == admin_id:
        raise ValueError("Você não pode excluir o próprio usuário administrador.")
    obter_usuario_por_id(usuario_id)
    with db_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM usuarios WHERE id=%s", (usuario_id,))
    registrar_auditoria(admin_id, "admin_deletou_usuario", "usuarios", usuario_id)


def listar_admin():
    with db_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM usuarios")
        total_usuarios = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM movimentacoes")
        total_movimentacoes = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM usuarios WHERE ativo=1")
        total_ativos = cursor.fetchone()["total"]
    return {
        "total_usuarios": total_usuarios,
        "total_movimentacoes": total_movimentacoes,
        "total_ativos": total_ativos,
        "usuarios": listar_usuarios_admin(),
    }
