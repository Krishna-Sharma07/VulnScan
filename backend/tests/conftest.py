import os
import uuid

import pytest
import sqlalchemy
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Deliberately a separate database from the dev "vulnscan" one (same
# postgres service/credentials, different name) so running the suite never
# touches data created by manual curl/browser verification in a dev session.
# Default assumes tests run inside the `api` container (`docker compose exec
# api pytest`), where "postgres" resolves via the compose network - override
# TEST_DATABASE_URL to run against something else.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://vulnscan:vulnscan@postgres:5432/vulnscan_test"
)

import app.db.base  # noqa: E402  - registers every model on Base.metadata
from app.db.base_class import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

test_engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False)


def _admin_connect():
    """Connects to the default db on the same server, autocommit, so we can
    CREATE DATABASE outside of any transaction (Postgres requires this)."""
    default_url = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/vulnscan"
    engine = create_engine(default_url, isolation_level="AUTOCOMMIT")
    return engine


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    test_db_name = TEST_DATABASE_URL.rsplit("/", 1)[1]
    admin_engine = _admin_connect()
    with admin_engine.connect() as conn:
        exists = conn.execute(
            sqlalchemy.text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": test_db_name},
        ).first()
        if not exists:
            conn.execute(sqlalchemy.text(f'CREATE DATABASE "{test_db_name}"'))
    admin_engine.dispose()

    # Drop/recreate tables every run rather than trusting leftover schema -
    # cheap for this table count, and avoids stale-schema surprises after a
    # model change.
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    test_engine.dispose()


@pytest.fixture()
def db_session():
    """One test = one DB transaction, rolled back at the end - so tests never
    see each other's data without needing to truncate tables between runs.
    Route handlers call `db.commit()` themselves, which would normally end
    the outer transaction early; the SAVEPOINT/restart trick below (the
    standard SQLAlchemy testing recipe) makes those inner commits only
    release a savepoint instead, keeping the real rollback available at the
    end of the test."""
    connection = test_engine.connect()
    outer_transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def no_celery(monkeypatch):
    """Scan creation dispatches a Celery task that launches real Docker
    scanner containers - never something a fast, self-contained test run
    should trigger. Stub the dispatch call itself; the task's own logic
    isn't exercised by these tests."""
    monkeypatch.setattr("app.api.routes.scans.run_scan.delay", lambda *a, **kw: None)


@pytest.fixture(autouse=True)
def no_ssrf_dns_lookup(monkeypatch):
    """create_scan calls the real SSRF guard (app/services/ssrf_guard.py),
    which does a real DNS lookup - most tests use made-up hostnames like
    scantest.example.com that don't resolve, so without this every scan-
    creation test would fail (or hang) on a real network call. Stubbed to a
    no-op by default; tests that specifically exercise the SSRF guard
    (test_scans.py, test_ssrf_guard.py) override it again per-test."""
    monkeypatch.setattr("app.api.routes.scans.assert_public_scan_target", lambda hostname: None)


def signup(client, email=None, password="testpassword123"):
    email = email or f"user_{uuid.uuid4().hex[:10]}@example.com"
    resp = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return resp.json(), password


def login(client, email, password):
    resp = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def auth_client(client):
    """A (client, auth_headers, user_json) tuple for a freshly signed-up,
    logged-in user - the shape almost every non-auth test needs."""
    user, password = signup(client)
    token = login(client, user["email"], password)
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers, user
