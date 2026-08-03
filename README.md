# VulnScan Pro

A SaaS-style web vulnerability scanner. Users register and DNS-verify a domain they own, then run OWASP Top 10-style security scans against it (or upload a code archive for static analysis) and get a severity-ranked PDF report back.

Built as much as a hands-on Docker/security learning project as a product - see `NOTES.md` for a full, dated build log covering the reasoning behind every architectural and security decision made along the way.

## Features

- **Live URL scanning** - a baseline (passive) scan via [OWASP ZAP](https://www.zaproxy.org/), or an opt-in "aggressive" scan that adds [sqlmap](https://sqlmap.org/) for active SQL-injection testing (supports an authenticated session cookie for scanning behind a login).
- **Uploaded-code scanning** - upload a `.zip` of a Python codebase and get static analysis from [bandit](https://bandit.readthedocs.io/) (insecure code patterns) and [safety](https://pyup.io/safety/) (known-vulnerable dependency versions). Nothing uploaded is ever executed.
- **Domain ownership verification** - a DNS TXT record challenge, required before any scan can target a domain, so the service can't be used to attack sites the submitter doesn't control.
- **SSRF-hardened scan execution** - scan targets are validated against private/internal IP ranges at request time *and* again immediately before a scan container launches, with the resolved IP pinned via `/etc/hosts` for the container's lifetime to close the DNS-rebinding window in between.
- **PDF reports** for every completed scan, downloadable from the app.
- **Freemium billing** - free/Pro/Enterprise tiers gating monthly scan volume and aggressive-scan access, with real (test-mode) Razorpay checkout for Pro.

## Stack

- **Backend**: FastAPI, PostgreSQL + SQLAlchemy + Alembic, Celery + Redis for async scan execution
- **Scanning**: Docker-orchestrated scanner containers (ZAP, sqlmap, bandit/safety), launched Docker-out-of-Docker from the Celery worker
- **Frontend**: React + TypeScript + Vite, React Router, Tailwind CSS
- **Billing**: Razorpay Orders API (server-side price table, HMAC-verified webhooks-equivalent via the checkout-verify endpoint)
- **CI**: GitHub Actions running the full backend (pytest) and frontend (vitest + production build) suites on every push/PR to `main`

## Running it locally

Requires Docker Desktop.

1. Copy the backend env template and fill in the required values:
   ```
   cp backend/.env.example backend/.env
   ```
   - `SECRET_KEY` and `AUTH_COOKIE_ENCRYPTION_KEY` are **required** - the app refuses to start without them (see `app/core/secrets.py`). Generate them with:
     ```
     python -c "import secrets; print(secrets.token_urlsafe(32))"
     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
     ```
   - `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` are only needed to test the Pro checkout flow - leave blank otherwise (everything else works fine without them).

2. Bring up the full stack:
   ```
   docker compose up --build
   ```
   This starts Postgres, Redis, the FastAPI API (auto-applies pending Alembic migrations on boot), the Celery worker, the React frontend, and a self-hosted [DVWA](https://github.com/digininja/DVWA) instance used as a controllable sqlmap test target.

3. Open the app at **http://localhost:5173**. Sign up, add a domain, complete DNS verification (or point at `example.com`/DVWA for a quick test), and run a scan.

   The first scan of each type (ZAP / sqlmap / code-scanner) builds its scanner image automatically - this only happens once and takes a few minutes.

### Running the tests

```
# Backend (from backend/, needs a Postgres instance - see backend/tests/conftest.py)
pytest

# Frontend
cd frontend && npm test
```

## Project structure

```
backend/          FastAPI app, Celery worker, Alembic migrations, pytest suite
frontend/          React + TypeScript SPA
scanner/            ZAP scanner image (build context)
sqlmap-scanner/    sqlmap scanner image (build context)
code-scanner/      bandit/safety scanner image (build context)
docker-compose.yml  Full local stack definition
NOTES.md            Dated, cumulative build log - the "why" behind every decision
```

## Known limitations

- No Razorpay webhook (server-to-server payment confirmation) - the checkout flow relies on the browser completing the final verify call. Needs a public HTTPS endpoint, so it's deferred until this is deployed somewhere real.
- Secrets are loaded from environment variables via a pluggable-provider seam (`app/core/secrets.py`), but no real KMS/secrets-manager backend is wired up yet.
- Code scanning only supports Python codebases (bandit/safety are both Python-ecosystem tools).
- This is a local/demo build, not deployed anywhere - see `NOTES.md` for the full reasoning trail if you want the details behind any of the above.
