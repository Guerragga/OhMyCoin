"""Explicit, idempotent database and local-demo initialization."""

import os
from pathlib import Path

import click
from werkzeug.security import generate_password_hash

from database import db_cursor


def init_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create missing tables without loading users or financial data."""
        script = Path(app.root_path) / "sql" / "schema.sql"
        with db_cursor(commit=True) as cursor:
            # The lock prevents two new replicas from applying the schema together.
            cursor.execute("SELECT GET_LOCK('ohmycoin-schema-init', 60) AS acquired")
            if cursor.fetchone()["acquired"] != 1:
                raise click.ClickException("Could not acquire schema initialization lock.")
            for statement in script.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    cursor.execute(statement)
        click.echo("Database schema is ready.")

    @app.cli.command("bootstrap-user")
    @click.option("--if-enabled", is_flag=True, help="Only run when BOOTSTRAP_USER_ENABLED=True.")
    def bootstrap_user(if_enabled):
        """Create one initial user from deployment secrets, without resetting it."""
        enabled = os.getenv("BOOTSTRAP_USER_ENABLED", "false").lower() in {"true", "1"}
        if if_enabled and not enabled:
            return
        if not enabled:
            raise click.ClickException("Set BOOTSTRAP_USER_ENABLED=True to authorize this one-time operation.")

        name = os.getenv("BOOTSTRAP_USER_NAME", "").strip()
        email = os.getenv("BOOTSTRAP_USER_EMAIL", "").strip().lower()
        password = os.getenv("BOOTSTRAP_USER_PASSWORD", "")
        if not name or not email or not password:
            raise click.ClickException("Bootstrap user name, email and password are required.")

        with db_cursor() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
            if cursor.fetchone():
                click.echo("Bootstrap user already exists; account preserved.")
                return

        from .services.users import criar_usuario

        criar_usuario(name, email, password)
        click.echo("Bootstrap user created. Disable bootstrap variables now.")

    @app.cli.command("seed-demo")
    @click.option("--if-enabled", is_flag=True, help="Only initialize when DEMO_MODE=True.")
    @click.option("--reset", is_flag=True, help="Replace only the fictional demo user's data.")
    def seed_demo(if_enabled, reset):
        if if_enabled and os.getenv("DEMO_MODE", "false").lower() not in {"true", "1"}:
            return
        if app.config["IS_PRODUCTION"]:
            raise click.ClickException("Demo initialization is disabled in production.")
        demo_email = os.getenv("DEMO_EMAIL", "demo@example.com").strip().lower()
        demo_name = os.getenv("DEMO_NAME", "Demo User").strip()
        demo_password = os.getenv("DEMO_PASSWORD", "Demo@12345")
        if not demo_email or not demo_name or not demo_password:
            raise click.ClickException("DEMO_EMAIL, DEMO_NAME and DEMO_PASSWORD cannot be empty.")
        with db_cursor(commit=True) as cursor:
            cursor.execute("SELECT GET_LOCK('ohmycoin-demo-seed', 30) AS acquired")
            if cursor.fetchone()["acquired"] != 1:
                raise click.ClickException("Could not acquire demo initialization lock.")
            cursor.execute("SELECT id FROM usuarios WHERE email=%s", (demo_email,))
            if cursor.fetchone() and not reset:
                click.echo("Demo already initialized; data preserved.")
                return
            cursor.execute("SET @demo_email = %s", (demo_email,))
            cursor.execute("SET @demo_name = %s", (demo_name,))
            cursor.execute("SET @demo_password_hash = %s", (generate_password_hash(demo_password),))
            script = Path(app.root_path) / "sql" / "demo_seed.sql"
            for statement in script.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    cursor.execute(statement)
            # Closing this connection releases the named lock, after commit.
        click.echo(f"Fictional demo initialized: {demo_email}")
