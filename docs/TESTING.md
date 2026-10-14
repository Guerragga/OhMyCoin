# Testing

## Layers

| Layer | Coverage |
| --- | --- |
| unit_tests | Money/date validation, closing-cycle boundaries, unsafe URLs, CSRF escaping/methods, headers, readiness failure and production configuration |
| tests | Real MySQL CRUD, authentication, session revocation, admin checks, tenant isolation, financial regressions, concurrency, demo authentication and page rendering |
| scripts/smoke_demo.py | Real HTTP cookies, CSRF, demo login, readiness and ten populated pages in Docker |
| scripts/browser_smoke.py | Chromium desktop/mobile widths, JavaScript/CSP errors, charts, page overflow and repeated cancelled deletion |

Concurrency tests make two real database calls in separate threads: duplicate debt payment must create one expense; two competing withdrawals must not overdraw savings.

Financial regression tests cover out-of-order and imported debt installments, reversal/reopening, no duplicate expenses, card rounding conservation, future committed credit limits and inactive-card obligations.

## Local unit checks

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q unit_tests
ruff check app tests unit_tests scripts config.py database.py run.py
bandit -r app config.py database.py
pip-audit -r requirements.txt
```

## Integration tests — destructive test database

Provide an empty MySQL 8.4 schema and user with create/truncate rights, exclusively for tests. Never use real data.

```bash
export DB_HOST=127.0.0.1
export DB_PORT=3306
export DB_NAME=ohmycoin_test
export DB_USER=ohmycoin_test
export DB_PASSWORD=YOUR_DISPOSABLE_TEST_PASSWORD
python -m pytest -q --cov=app --cov-report=term-missing
```

Test setup refuses a database name without the `_test` suffix. It creates the schema and truncates its tables between tests. The name check supplements, but cannot replace, isolated credentials.

## Docker/browser checks

```bash
docker compose up --build -d --wait
python scripts/smoke_demo.py
python -m pip install playwright==1.63.0
python -m playwright install --with-deps chromium
python scripts/browser_smoke.py
```

Only run these against the fictional local demo. Browser checks deliberately click and cancel delete confirmations. Screenshots go to ignored `browser-artifacts/`.

## CI

The test job runs compilation, Ruff, Pytest, Bandit and pip-audit using disposable MySQL. The Docker job builds the actual image, checks startup, demo authentication, populated pages and restart, and runs Chromium checks. Screenshots are uploaded for seven days.

Review the checks on the exact release commit; a previously green commit does not validate subsequent changes. Scans are not disabled to get a green result.

## Remaining scope

Chromium smoke checks do not establish WCAG compliance, complete keyboard accessibility, all browser compatibility, realistic load performance or penetration-test coverage. Manual visual review and additional browser/accessibility tooling remain useful before a public hosted deployment.
