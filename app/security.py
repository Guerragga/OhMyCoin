import secrets

from flask import abort, g, request, session
from markupsafe import Markup


def init_security(app) -> None:
    """Register CSRF protection and HTTP security headers."""

    @app.before_request
    def prepare_request_security():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.before_request
    def protect_csrf():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return

        session_token = session.get("csrf_token")
        request_token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        if (
            not session_token
            or not request_token
            or not secrets.compare_digest(str(session_token).encode(), str(request_token).encode())
        ):
            abort(400, description="Token CSRF inválido ou ausente.")

    @app.after_request
    def apply_security_headers(response):
        if not app.config.get("ENABLE_SECURITY_HEADERS", True):
            return response

        nonce = getattr(g, "csp_nonce", "")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()",
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            f"script-src 'self' https://cdn.jsdelivr.net 'nonce-{nonce}'; "
            "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://cdn.jsdelivr.net data:; "
            "connect-src 'self'; " + ("upgrade-insecure-requests" if app.config.get("IS_PRODUCTION") else ""),
        )
        if request.endpoint != "static":
            response.headers.setdefault("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            response.headers.setdefault("Pragma", "no-cache")

        if request.is_secure and app.config.get("IS_PRODUCTION"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.context_processor
    def security_context():
        def csrf_token():
            if "csrf_token" not in session:
                session["csrf_token"] = secrets.token_urlsafe(32)
            return session["csrf_token"]

        def csrf_input():
            return Markup('<input type="hidden" name="csrf_token" value="{}">').format(csrf_token())

        def csp_nonce():
            return getattr(g, "csp_nonce", "")

        return {
            "csrf_token": csrf_token,
            "csrf_input": csrf_input,
            "csp_nonce": csp_nonce,
        }

    @app.errorhandler(400)
    def bad_request(_error):
        return "Requisição inválida. Atualize a página e tente novamente.", 400

    @app.errorhandler(413)
    def request_too_large(_error):
        return "Arquivo ou requisição muito grande.", 413
