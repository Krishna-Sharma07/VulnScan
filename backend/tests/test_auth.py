from tests.conftest import login, signup


def test_signup_returns_user_without_password(client):
    user, _ = signup(client, email="new@example.com", password="testpassword123")
    assert user["email"] == "new@example.com"
    assert user["plan"] == "free"
    assert "hashed_password" not in user
    assert "password" not in user


def test_signup_duplicate_email_rejected(client):
    signup(client, email="dupe@example.com")
    resp = client.post(
        "/api/auth/signup", json={"email": "dupe@example.com", "password": "testpassword123"}
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Email already registered"


def test_signup_password_too_short_is_422_with_array_detail(client):
    resp = client.post(
        "/api/auth/signup", json={"email": "short@example.com", "password": "abc"}
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, list)
    assert any("at least 8 characters" in d["msg"] for d in detail)


def test_login_success_returns_bearer_token(client):
    user, password = signup(client, email="loginok@example.com")
    token = login(client, user["email"], password)
    assert isinstance(token, str) and len(token) > 0


def test_login_wrong_password_is_401(client):
    user, _ = signup(client, email="wrongpw@example.com")
    resp = client.post(
        "/api/auth/login",
        data={"username": user["email"], "password": "not-the-password"},
    )
    assert resp.status_code == 401


def test_login_unknown_email_is_401(client):
    resp = client.post(
        "/api/auth/login",
        data={"username": "nobody@example.com", "password": "whatever123"},
    )
    assert resp.status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(auth_client):
    client, headers, user = auth_client
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == user["id"]
