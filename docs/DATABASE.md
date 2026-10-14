# Database

## Fresh installations

`migrations/001_schema.sql` defines the canonical MySQL 8.4 schema with InnoDB, utf8mb4 and utf8mb4_unicode_ci. Connector and seed use the same collation to avoid MySQL user-variable comparison failures.

This file is a baseline for an empty database. `flask init-db` applies that
baseline explicitly and is suitable for a newly provisioned database. CREATE
TABLE IF NOT EXISTS does **not** upgrade existing tables. Do not point the new
code at an old private/personal database without a separately reviewed
migration and backup. Local fictional environments may be recreated explicitly.

## Tables

| Group | Tables |
| --- | --- |
| Identity | usuarios, login_attempts, audit_logs |
| Ledger | contas, categorias, movimentacoes |
| Planning | previsoes_mensais, caixinhas |
| Credit | cartoes_credito, compras_cartao |
| Debts | dividas, pagamentos_dividas |

Financial rows carry usuario_id. Service validation checks related ownership. Foreign keys enforce reference existence; optional account/category links use SET NULL to preserve historical records. User deletion cascades owned financial data; audit user links become NULL.

Unique constraints cover user email, per-user account/category/card names and each paid debt installment. Checks cover monetary bounds/nonnegative reserves, installment counts and day ranges. Indexes cover common user/date, account, category, card and login-window lookups.

## Demo

Run `python -m flask --app run seed-demo` in an initialized development database. It generates a real Werkzeug password hash for the documented fictional credential and executes `002_seed_demo.sql` inside a transaction. It refuses production and preserves an existing demo account unless `--reset` is explicit.

Do not execute the seed SQL directly: its password variable is supplied by the CLI. No real database dump or personal dataset is needed.

## Reset and backup

`docker compose down` preserves the named MySQL volume.

**Destructive, local fictional data only:** `docker compose down -v` removes the Compose database volume. A subsequent `docker compose up --build` recreates the schema and demo.

The integration test suite truncates all configured test tables. It refuses databases whose names do not end in `_test`. Use a separate disposable user and schema; the name guard alone is not a backup or access-control boundary.
