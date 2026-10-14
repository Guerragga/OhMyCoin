# Architecture

## Request and domain boundaries

Flask's application factory installs security hooks, routes, CLI commands, template filters and health endpoints. The route layer performs request handling, session validation, authorization and user feedback. Services own validation, SQL and domain rules. Services receive the authenticated user ID explicitly.

| Module | Responsibility |
| --- | --- |
| common | Money, dates, text and image URL validation |
| users | Passwords, account records, settings, throttling and admin operations |
| accounts / categories | Owned accounts, balances and classification |
| transactions | Real entries and the unified card-purchase read model |
| cards | Purchases, invoice schedule, rounding and estimated committed limit |
| debts | Schedules, payment identity, payment creation and early payment |
| savings / forecasts | External reserves and independently entered budgets |
| dashboard | Cash flow, commitments and presentation aggregations |
| security | CSRF and HTTP headers |
| cli | Idempotent fictional demo initialization |

`services/__init__.py` is an explicit facade for routes. Cross-domain imports go directly to the defining module, avoiding circular imports through the facade.

## Persistence and transactions

SQL remains explicit. Runtime values, including optional filters, are connector parameters; table/column names are not sourced from requests. `db_cursor` commits only on success, rolls back exceptions, closes resources and translates expected duplicate/reference errors into validation errors.

Debt payment and reversal lock the parent debt before payment rows. Savings movements lock the goal before reading its balance. Duplicate debt payments also have a unique database constraint.

The database guarantees reference existence; optional references are not composite tenant foreign keys. Services therefore validate ownership before writes. Raw database access is a privileged trust boundary; expose neither the DB credentials nor unrestricted SQL endpoints.

## Runtime

Compose runs MySQL 8.4 and a non-root Gunicorn web container. Only loopback port 5000 is published. MySQL initialization runs on a fresh named volume. The web startup invokes `seed-demo --if-enabled` and then Gunicorn with preload.

Demo initialization uses a MySQL named lock and a transaction. It is idempotent by default; explicit `--reset` replaces that account's fictional data. Production rejects demo initialization.

An automatically generated development session key lives only in memory and changes on restart. Gunicorn preload shares that key across workers. Production must supply a persistent secret.

## Trade-offs

- The app is synchronous and opens connections per operation; connection pooling and query batching need profiling before scaling.
- Some dashboard aggregations use repeated per-account/card queries. Performance under large datasets is not established.
- Listing limits are explicit but not a complete pagination UI.
- The schema is a fresh-install baseline, not an automatic upgrade mechanism.
- Bootstrap and Chart.js are pinned CDN assets; rendering depends on CDN availability. Self-hosting assets and adding integrity hashes are further supply-chain improvements.
- Browser checks cover Chromium at desktop/mobile widths, not every browser/device or WCAG compliance.
