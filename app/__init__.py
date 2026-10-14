from decimal import Decimal, InvalidOperation

from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from database import database_ready
from .security import init_security


def moeda(valor):
    try:
        numero = Decimal(str(valor or 0))
    except (InvalidOperation, TypeError, ValueError):
        numero = Decimal("0")
    texto = f"R$ {numero:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def percentual(valor):
    try:
        numero = Decimal(str(valor or 0))
    except (InvalidOperation, TypeError, ValueError):
        numero = Decimal("0")
    return f"{numero:.2f}%".replace(".", ",")


def data_br(valor):
    if not valor:
        return "-"
    return valor.strftime("%d/%m/%Y") if hasattr(valor, "strftime") else str(valor)


def mes_br(valor):
    if not valor:
        return "-"
    texto = str(valor)
    if len(texto) >= 7:
        ano, mes = texto[:4], texto[5:7]
        return f"{mes}/{ano}"
    return texto


def create_app():
    Config.validate_security()

    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY

    if app.config.get("TRUST_PROXY_HEADERS"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    init_security(app)
    from .cli import init_cli

    init_cli(app)

    from .routes import bp

    app.register_blueprint(bp)

    app.jinja_env.filters["moeda"] = moeda
    app.jinja_env.filters["percentual"] = percentual
    app.jinja_env.filters["data_br"] = data_br
    app.jinja_env.filters["mes_br"] = mes_br

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    @app.get("/readyz")
    def readyz():
        ready = database_ready()
        return jsonify(status="ready" if ready else "unavailable"), 200 if ready else 503

    return app
