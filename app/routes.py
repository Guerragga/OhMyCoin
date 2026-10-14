from functools import wraps
import secrets
import hashlib

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from . import services

bp = Blueprint("finance", __name__)


@bp.before_request
def validate_month_filter():
    if request.args.get("mes"):
        try:
            services.normalizar_mes(request.args["mes"])
        except ValueError:
            from flask import abort

            abort(400)


def usuario_id_atual():
    return session.get("usuario_id")


def client_ip():
    return (request.remote_addr or "unknown")[:45]


def validar_sessao_atual():
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return None
    usuario = services.obter_usuario_por_id(usuario_id)
    if (
        not usuario
        or not usuario.get("ativo")
        or session.get("auth_version") != hashlib.sha256(usuario["senha"].encode()).hexdigest()
    ):
        session.clear()
        return None
    session["usuario_nome"] = usuario.get("nome")
    session["usuario_nivel"] = usuario.get("nivel_acesso", "USER")
    session["usuario_avatar"] = usuario.get("avatar_emoji") or "💰"
    session["usuario_tema"] = usuario.get("tema") or "escuro"
    return usuario


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not validar_sessao_atual():
            flash("Você precisa estar logado para acessar essa página.", "warning")
            return redirect(url_for("finance.login"))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        usuario = validar_sessao_atual()
        if not usuario:
            flash("Você precisa estar logado para acessar essa página.", "warning")
            return redirect(url_for("finance.login"))
        if usuario.get("nivel_acesso") != "ADMIN":
            flash("Acesso restrito a administradores.", "danger")
            return redirect(url_for("finance.dashboard"))
        return view(*args, **kwargs)

    return wrapped_view


@bp.route("/")
def home():
    if "usuario_id" in session:
        return redirect(url_for("finance.dashboard"))
    return redirect(url_for("finance.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("password") or ""
        ip = client_ip()
        if not email or not senha or len(email) > 120 or len(senha) > 128:
            flash("Preencha e-mail e senha.", "danger")
            return redirect(url_for("finance.login"))
        try:
            services.verificar_rate_limit_login(email, ip)
        except ValueError as erro:
            flash(str(erro), "danger")
            return redirect(url_for("finance.login"))
        usuario = services.obter_usuario_por_email(email)
        valid_password = services.senha_confere(usuario["senha"] if usuario else None, senha)
        if not usuario or not valid_password:
            services.registrar_login_falha(email, ip)
            services.registrar_auditoria(None, "login_falha", "usuarios")
            flash("E-mail ou senha inválidos.", "danger")
            return redirect(url_for("finance.login"))
        services.limpar_login_falhas(email, ip)
        session.clear()
        session.permanent = True
        session["csrf_token"] = secrets.token_urlsafe(32)
        session["usuario_id"] = usuario["id"]
        session["auth_version"] = hashlib.sha256(usuario["senha"].encode()).hexdigest()
        session["usuario_nome"] = usuario["nome"]
        session["usuario_nivel"] = usuario.get("nivel_acesso", "USER")
        session["usuario_avatar"] = usuario.get("avatar_emoji") or "💰"
        session["usuario_tema"] = usuario.get("tema") or "escuro"
        services.registrar_auditoria(usuario["id"], "login_sucesso", "usuarios", usuario["id"])
        flash("Login realizado com sucesso.", "success")
        return redirect(url_for("finance.dashboard"))
    return render_template("login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if not current_app.config.get("ALLOW_REGISTRATION", True):
        flash("Novos cadastros estão temporariamente desabilitados.", "info")
        return redirect(url_for("finance.login"))

    if request.method == "POST":
        try:
            senha = request.form.get("password")
            confirmar = request.form.get("password_confirm")
            if senha != confirmar:
                raise ValueError("A confirmação de senha não confere.")
            services.criar_usuario(
                nome=request.form.get("name"),
                email=request.form.get("email"),
                senha=senha,
            )
            flash("Conta criada com sucesso. Faça login para continuar.", "success")
            return redirect(url_for("finance.login"))
        except ValueError as erro:
            flash(str(erro), "danger")
    return render_template("register.html")


@bp.route("/logout", methods=["POST"])
def logout():
    usuario_id = session.get("usuario_id")
    services.registrar_auditoria(usuario_id, "logout", "usuarios", usuario_id)
    session.clear()
    flash("Você saiu da conta.", "info")
    return redirect(url_for("finance.login"))


@bp.route("/dashboard")
@login_required
def dashboard():
    mes = request.args.get("mes") or services.mes_atual()
    try:
        resumo = services.obter_resumo_dashboard(usuario_id_atual(), mes)
    except ValueError as erro:
        flash(str(erro), "danger")
        resumo = services.obter_resumo_dashboard(usuario_id_atual())
    return render_template("dashboard.html", resumo=resumo)


@bp.route("/admin")
@admin_required
def admin():
    return render_template("admin.html", **services.listar_admin())


@bp.route("/admin/usuarios/<int:alvo_id>/editar", methods=["POST"])
@admin_required
def admin_editar_usuario(alvo_id):
    try:
        services.atualizar_usuario_admin(usuario_id_atual(), alvo_id, request.form)
        if alvo_id == usuario_id_atual():
            usuario = services.obter_usuario_por_id(alvo_id)
            session["usuario_nome"] = usuario.get("nome")
            session["usuario_nivel"] = usuario.get("nivel_acesso", "ADMIN")
        flash("Usuário atualizado com sucesso.", "success")
    except ValueError as erro:
        flash(str(erro), "danger")
    return redirect(url_for("finance.admin"))


@bp.route("/admin/usuarios/<int:alvo_id>/deletar", methods=["POST"])
@admin_required
def admin_deletar_usuario(alvo_id):
    try:
        services.deletar_usuario_admin(usuario_id_atual(), alvo_id)
        flash("Usuário excluído com sucesso.", "success")
    except ValueError as erro:
        flash(str(erro), "danger")
    return redirect(url_for("finance.admin"))


@bp.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    usuario = services.obter_usuario_por_id(usuario_id_atual())
    if request.method == "POST":
        acao = request.form.get("acao")
        try:
            if acao == "dados":
                nome, avatar = services.atualizar_perfil(usuario_id_atual(), request.form)
                session["usuario_nome"] = nome
                session["usuario_avatar"] = avatar
                flash("Perfil atualizado com sucesso.", "success")
            elif acao == "senha":
                services.alterar_senha_perfil(usuario_id_atual(), request.form)
                flash("Senha alterada com sucesso.", "success")
            return redirect(url_for("finance.perfil"))
        except ValueError as erro:
            flash(str(erro), "danger")
    return render_template("perfil.html", usuario=usuario)


@bp.route("/configuracoes", methods=["GET", "POST"])
@login_required
def configuracoes():
    if request.method == "POST":
        try:
            tema = services.atualizar_configuracoes(usuario_id_atual(), request.form)
            session["usuario_tema"] = tema
            flash("Configurações salvas com sucesso.", "success")
            return redirect(url_for("finance.configuracoes"))
        except ValueError as erro:
            flash(str(erro), "danger")
    return render_template(
        "configuracoes.html",
        config=services.configuracoes_usuario(usuario_id_atual()),
        chart_flags=services.CHART_FLAGS,
    )


@bp.route("/categorias", methods=["GET", "POST"])
@login_required
def categorias():
    if request.method == "POST":
        try:
            services.criar_categoria(
                usuario_id_atual(), request.form.get("nome"), request.form.get("tipo"), request.form.get("descricao")
            )
            flash("Categoria criada com sucesso.", "success")
            return redirect(url_for("finance.categorias"))
        except ValueError as erro:
            flash(str(erro), "danger")
    return render_template("categorias.html", categorias=services.listar_categorias(usuario_id_atual()), categoria=None)


@bp.route("/categorias/<int:categoria_id>/editar", methods=["GET", "POST"])
@login_required
def editar_categoria(categoria_id):
    try:
        categoria = services.obter_categoria(usuario_id_atual(), categoria_id)
        if request.method == "POST":
            services.atualizar_categoria(
                usuario_id_atual(),
                categoria_id,
                request.form.get("nome"),
                request.form.get("tipo"),
                request.form.get("descricao"),
            )
            flash("Categoria atualizada com sucesso.", "success")
            return redirect(url_for("finance.categorias"))
    except ValueError as erro:
        flash(str(erro), "danger")
        return redirect(url_for("finance.categorias"))
    return render_template(
        "categorias.html", categorias=services.listar_categorias(usuario_id_atual()), categoria=categoria
    )


@bp.route("/categorias/<int:categoria_id>/deletar", methods=["POST"])
@login_required
def deletar_categoria(categoria_id):
    try:
        services.deletar_categoria(usuario_id_atual(), categoria_id)
        flash("Categoria removida.", "success")
    except ValueError as erro:
        flash(str(erro), "danger")
    return redirect(url_for("finance.categorias"))


@bp.route("/contas", methods=["GET", "POST"])
@login_required
def contas():
    if request.method == "POST":
        try:
            services.salvar_conta(usuario_id_atual(), request.form)
            flash("Conta salva com sucesso.", "success")
            return redirect(url_for("finance.contas"))
        except ValueError as erro:
            flash(str(erro), "danger")
    return render_template("contas.html", contas=services.listar_contas(usuario_id_atual()), conta=None)


@bp.route("/contas/<int:conta_id>")
@login_required
def detalhe_conta(conta_id):
    mes = request.args.get("mes") or services.mes_atual()
    try:
        conta = services.obter_conta(usuario_id_atual(), conta_id)
        filtros = services.filtros_movimentacoes_from_args(request.args, mes)
        filtros["conta_id"] = conta_id
    except ValueError as erro:
        flash(str(erro), "danger")
        return redirect(url_for("finance.contas"))
    return render_template(
        "conta_detalhe.html",
        conta=conta,
        movimentacoes=services.listar_movimentacoes_conta(usuario_id_atual(), conta_id, filtros),
        mes=filtros.get("mes", mes),
        filtros=filtros,
    )


@bp.route("/contas/<int:conta_id>/editar", methods=["GET", "POST"])
@login_required
def editar_conta(conta_id):
    try:
        conta = services.obter_conta(usuario_id_atual(), conta_id)
        if request.method == "POST":
            services.salvar_conta(usuario_id_atual(), request.form, conta_id)
            flash("Conta atualizada com sucesso.", "success")
            return redirect(url_for("finance.contas"))
    except ValueError as erro:
        flash(str(erro), "danger")
        return redirect(url_for("finance.contas"))
    return render_template("contas.html", contas=services.listar_contas(usuario_id_atual()), conta=conta)


@bp.route("/contas/<int:conta_id>/deletar", methods=["POST"])
@login_required
def deletar_conta(conta_id):
    try:
        services.deletar_conta(usuario_id_atual(), conta_id)
        flash("Conta removida com sucesso.", "success")
    except ValueError as erro:
        flash(str(erro), "danger")
    return redirect(url_for("finance.contas"))


@bp.route("/movimentacoes", methods=["GET", "POST"])
@login_required
def movimentacoes():
    if request.method == "POST":
        try:
            services.salvar_movimentacao(usuario_id_atual(), request.form)
            flash("Movimentação registrada com sucesso.", "success")
            return redirect(
                url_for(
                    "finance.movimentacoes",
                    mes=request.form.get("mes_redirect") or request.form.get("data_movimentacao", "")[:7],
                )
            )
        except ValueError as erro:
            flash(str(erro), "danger")
    mes = request.args.get("mes") or services.mes_atual()
    try:
        filtros = services.filtros_movimentacoes_from_args(request.args, mes)
        mes = filtros.get("mes", mes)
    except ValueError as erro:
        flash(str(erro), "danger")
        mes = services.mes_atual()
        filtros = services.filtros_movimentacoes_from_args({}, mes)
    return render_template(
        "movimentacoes.html",
        movimentacoes=services.listar_movimentacoes(usuario_id_atual(), filtros),
        categorias=services.listar_categorias(usuario_id_atual()),
        contas=services.listar_contas(usuario_id_atual(), apenas_ativas=True),
        cartoes=services.listar_cartoes(usuario_id_atual(), apenas_ativos=True, ano_mes=mes),
        movimentacao=None,
        mes=mes,
        filtros=filtros,
    )


@bp.route("/movimentacoes/<int:movimentacao_id>/editar", methods=["GET", "POST"])
@login_required
def editar_movimentacao(movimentacao_id):
    try:
        movimentacao = services.obter_movimentacao(usuario_id_atual(), movimentacao_id)
        if request.method == "POST":
            services.salvar_movimentacao(usuario_id_atual(), request.form, movimentacao_id)
            flash("Movimentação atualizada com sucesso.", "success")
            return redirect(url_for("finance.movimentacoes", mes=request.form.get("data_movimentacao", "")[:7]))
    except ValueError as erro:
        flash(str(erro), "danger")
        return redirect(url_for("finance.movimentacoes"))
    return render_template(
        "movimentacoes.html",
        movimentacoes=services.listar_movimentacoes(usuario_id_atual(), {}),
        categorias=services.listar_categorias(usuario_id_atual()),
        contas=services.listar_contas(usuario_id_atual(), apenas_ativas=True),
        cartoes=services.listar_cartoes(usuario_id_atual(), apenas_ativos=True),
        movimentacao=movimentacao,
        mes="",
        filtros={},
    )


@bp.route("/movimentacoes/<int:movimentacao_id>/deletar", methods=["POST"])
@login_required
def deletar_movimentacao(movimentacao_id):
    try:
        services.deletar_movimentacao(usuario_id_atual(), movimentacao_id)
        flash("Movimentação removida com sucesso.", "success")
    except ValueError as erro:
        flash(str(erro), "danger")
    return redirect(url_for("finance.movimentacoes"))


@bp.route("/previsoes", methods=["GET", "POST"])
@login_required
def previsoes():
    mes = request.args.get("mes") or request.form.get("ano_mes") or services.mes_atual()
    if request.method == "POST":
        try:
            services.salvar_previsao(usuario_id_atual(), request.form)
            flash("Previsão salva com sucesso.", "success")
            return redirect(url_for("finance.previsoes", mes=request.form.get("ano_mes") or mes))
        except ValueError as erro:
            flash(str(erro), "danger")
    try:
        mes = services.normalizar_mes(mes)
    except ValueError:
        mes = services.mes_atual()
    return render_template(
        "previsoes.html",
        previsoes=services.listar_previsoes(usuario_id_atual(), mes),
        categorias=services.listar_categorias(usuario_id_atual()),
        contas=services.listar_contas(usuario_id_atual(), apenas_ativas=True),
        previsao=None,
        mes=mes,
    )


@bp.route("/previsoes/<int:previsao_id>/editar", methods=["GET", "POST"])
@login_required
def editar_previsao(previsao_id):
    try:
        previsao = services.obter_previsao(usuario_id_atual(), previsao_id)
        mes = previsao["ano_mes"]
        if request.method == "POST":
            services.salvar_previsao(usuario_id_atual(), request.form, previsao_id)
            flash("Previsão atualizada com sucesso.", "success")
            return redirect(url_for("finance.previsoes", mes=request.form.get("ano_mes") or mes))
    except ValueError as erro:
        flash(str(erro), "danger")
        return redirect(url_for("finance.previsoes"))
    return render_template(
        "previsoes.html",
        previsoes=services.listar_previsoes(usuario_id_atual(), mes),
        categorias=services.listar_categorias(usuario_id_atual()),
        contas=services.listar_contas(usuario_id_atual(), apenas_ativas=True),
        previsao=previsao,
        mes=mes,
    )


@bp.route("/previsoes/<int:previsao_id>/deletar", methods=["POST"])
@login_required
def deletar_previsao(previsao_id):
    mes = request.form.get("mes") or services.mes_atual()
    try:
        services.deletar_previsao(usuario_id_atual(), previsao_id)
        flash("Previsão removida com sucesso.", "success")
    except ValueError as erro:
        flash(str(erro), "danger")
    return redirect(url_for("finance.previsoes", mes=mes))


@bp.route("/cartoes", methods=["GET", "POST"])
@login_required
def cartoes():
    if request.method == "POST":
        try:
            services.salvar_cartao(usuario_id_atual(), request.form)
            flash("Cartão salvo com sucesso.", "success")
            return redirect(url_for("finance.cartoes"))
        except ValueError as erro:
            flash(str(erro), "danger")
    mes = request.args.get("mes") or services.mes_atual()
    return render_template(
        "cartoes.html",
        cartoes=services.listar_cartoes(usuario_id_atual(), ano_mes=mes),
        compras=services.listar_compras_cartao(usuario_id_atual(), limite=25),
        parcelas_mes=services.parcelas_cartao_mes(usuario_id_atual(), mes),
        faturas_geral=services.resumo_faturas_geral(usuario_id_atual(), mes, 4),
        categorias=services.listar_categorias(usuario_id_atual(), tipo="despesa"),
        cartao=None,
        mes=mes,
    )


@bp.route("/cartoes/<int:cartao_id>/editar", methods=["GET", "POST"])
@login_required
def editar_cartao(cartao_id):
    try:
        cartao = services.obter_cartao(usuario_id_atual(), cartao_id)
        if request.method == "POST":
            services.salvar_cartao(usuario_id_atual(), request.form, cartao_id)
            flash("Cartão atualizado com sucesso.", "success")
            return redirect(url_for("finance.cartoes"))
    except ValueError as erro:
        flash(str(erro), "danger")
        return redirect(url_for("finance.cartoes"))
    mes = request.args.get("mes") or services.mes_atual()
    return render_template(
        "cartoes.html",
        cartoes=services.listar_cartoes(usuario_id_atual(), ano_mes=mes),
        compras=services.listar_compras_cartao(usuario_id_atual(), limite=25),
        parcelas_mes=services.parcelas_cartao_mes(usuario_id_atual(), mes),
        faturas_geral=services.resumo_faturas_geral(usuario_id_atual(), mes, 4),
        categorias=services.listar_categorias(usuario_id_atual(), tipo="despesa"),
        cartao=cartao,
        mes=mes,
    )


@bp.route("/cartoes/<int:cartao_id>")
@login_required
def detalhe_cartao(cartao_id):
    mes = request.args.get("mes") or services.mes_atual()
    try:
        cartao = services.obter_cartao(usuario_id_atual(), cartao_id)
    except ValueError as erro:
        flash(str(erro), "danger")
        return redirect(url_for("finance.cartoes"))
    return render_template(
        "cartao_detalhe.html",
        cartao=cartao,
        compras=services.listar_compras_cartao(usuario_id_atual(), cartao_id=cartao_id, limite=300),
        parcelas_mes=services.parcelas_cartao_mes(usuario_id_atual(), mes, cartao_id=cartao_id),
        faturas=services.resumo_faturas_geral(usuario_id_atual(), mes, 6),
        mes=mes,
    )


@bp.route("/cartoes/<int:cartao_id>/deletar", methods=["POST"])
@login_required
def deletar_cartao(cartao_id):
    try:
        services.deletar_cartao(usuario_id_atual(), cartao_id)
        flash("Cartão excluído com sucesso.", "success")
    except ValueError as erro:
        flash(str(erro), "danger")
    return redirect(url_for("finance.cartoes"))


@bp.route("/cartoes/compras", methods=["POST"])
@login_required
def compra_cartao():
    try:
        services.registrar_compra_cartao(usuario_id_atual(), request.form)
        flash("Compra do cartão registrada com sucesso.", "success")
    except ValueError as erro:
        flash(str(erro), "danger")
    return redirect(url_for("finance.cartoes"))


@bp.route("/cartoes/compras/<int:compra_id>/deletar", methods=["POST"])
@login_required
def deletar_compra_cartao(compra_id):
    try:
        services.deletar_compra_cartao(usuario_id_atual(), compra_id)
        flash("Compra removida com sucesso.", "success")
    except ValueError as erro:
        flash(str(erro), "danger")
    return redirect(url_for("finance.cartoes"))


@bp.route("/dividas", methods=["GET", "POST"])
@login_required
def dividas():
    mes = request.args.get("mes") or services.mes_atual()
    if request.method == "POST":
        try:
            services.salvar_divida(usuario_id_atual(), request.form)
            flash("Dívida parcelada salva com sucesso.", "success")
            return redirect(url_for("finance.dividas", mes=mes))
        except ValueError as erro:
            flash(str(erro), "danger")
    return render_template(
        "dividas.html",
        dividas=services.listar_dividas(usuario_id_atual()),
        parcelas_mes=services.parcelas_dividas_mes(usuario_id_atual(), mes),
        categorias=services.listar_categorias(usuario_id_atual(), tipo="despesa"),
        contas=services.listar_contas(usuario_id_atual(), apenas_ativas=True),
        divida=None,
        mes=mes,
    )


@bp.route("/dividas/<int:divida_id>/editar", methods=["GET", "POST"])
@login_required
def editar_divida(divida_id):
    mes = request.args.get("mes") or services.mes_atual()
    try:
        divida = services.obter_divida(usuario_id_atual(), divida_id)
        if request.method == "POST":
            services.salvar_divida(usuario_id_atual(), request.form, divida_id)
            flash("Dívida atualizada com sucesso.", "success")
            return redirect(url_for("finance.dividas", mes=mes))
    except ValueError as erro:
        flash(str(erro), "danger")
        return redirect(url_for("finance.dividas", mes=mes))
    return render_template(
        "dividas.html",
        dividas=services.listar_dividas(usuario_id_atual()),
        parcelas_mes=services.parcelas_dividas_mes(usuario_id_atual(), mes),
        categorias=services.listar_categorias(usuario_id_atual(), tipo="despesa"),
        contas=services.listar_contas(usuario_id_atual(), apenas_ativas=True),
        divida=divida,
        mes=mes,
    )


@bp.route("/dividas/<int:divida_id>/pagar-parcela", methods=["POST"])
@login_required
def pagar_parcela_divida(divida_id):
    mes = request.form.get("mes") or services.mes_atual()
    try:
        services.pagar_parcela_divida(usuario_id_atual(), divida_id, mes)
        flash("Parcela marcada como paga e despesa criada.", "success")
    except ValueError as erro:
        flash(str(erro), "danger")
    return redirect(url_for("finance.dividas", mes=mes))


@bp.route("/dividas/<int:divida_id>/antecipar-parcela", methods=["POST"])
@login_required
def antecipar_parcela_divida(divida_id):
    mes = request.form.get("mes") or services.mes_atual()
    try:
        numero = services.antecipar_proxima_parcela_divida(usuario_id_atual(), divida_id)
        flash(f"Parcela {numero} antecipada e registrada como saída real de hoje.", "success")
    except ValueError as erro:
        flash(str(erro), "danger")
    return redirect(url_for("finance.dividas", mes=mes))


@bp.route("/dividas/<int:divida_id>/deletar", methods=["POST"])
@login_required
def deletar_divida(divida_id):
    try:
        services.deletar_divida(usuario_id_atual(), divida_id)
        flash("Dívida removida com sucesso.", "success")
    except ValueError as erro:
        flash(str(erro), "danger")
    return redirect(url_for("finance.dividas"))


@bp.route("/caixinhas", methods=["GET", "POST"])
@login_required
def caixinhas():
    if request.method == "POST":
        try:
            services.salvar_caixinha(usuario_id_atual(), request.form)
            flash("Caixinha criada com sucesso.", "success")
            return redirect(url_for("finance.caixinhas"))
        except ValueError as erro:
            flash(str(erro), "danger")
    return render_template("caixinhas.html", caixinhas=services.listar_caixinhas(usuario_id_atual()), caixinha=None)


@bp.route("/caixinhas/<int:caixinha_id>/editar", methods=["GET", "POST"])
@login_required
def editar_caixinha(caixinha_id):
    try:
        caixinha = services.obter_caixinha(usuario_id_atual(), caixinha_id)
        if request.method == "POST":
            services.salvar_caixinha(usuario_id_atual(), request.form, caixinha_id)
            flash("Caixinha atualizada com sucesso.", "success")
            return redirect(url_for("finance.caixinhas"))
    except ValueError as erro:
        flash(str(erro), "danger")
        return redirect(url_for("finance.caixinhas"))
    return render_template("caixinhas.html", caixinhas=services.listar_caixinhas(usuario_id_atual()), caixinha=caixinha)


@bp.route("/caixinhas/<int:caixinha_id>/movimentar", methods=["POST"])
@login_required
def movimentar_caixinha(caixinha_id):
    try:
        services.movimentar_caixinha(
            usuario_id_atual(), caixinha_id, request.form.get("valor"), request.form.get("acao")
        )
        flash("Caixinha atualizada com sucesso.", "success")
    except ValueError as erro:
        flash(str(erro), "danger")
    return redirect(url_for("finance.caixinhas"))


@bp.route("/caixinhas/<int:caixinha_id>/deletar", methods=["POST"])
@login_required
def deletar_caixinha(caixinha_id):
    try:
        services.deletar_caixinha(usuario_id_atual(), caixinha_id)
        flash("Caixinha removida com sucesso.", "success")
    except ValueError as erro:
        flash(str(erro), "danger")
    return redirect(url_for("finance.caixinhas"))
