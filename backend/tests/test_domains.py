DOMAINS_URL = "/api/domains"


def test_register_domain_lowercases_hostname_and_starts_unverified(auth_client):
    client, headers, _ = auth_client
    resp = client.post(DOMAINS_URL, json={"hostname": "Example.COM"}, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["hostname"] == "example.com"
    assert data["verified"] is False
    assert data["has_auth_cookie"] is False


def test_list_domains_only_returns_current_users_domains(client):
    from tests.conftest import login, signup

    user_a, pw_a = signup(client, email="ownerA@example.com")
    headers_a = {"Authorization": f"Bearer {login(client, user_a['email'], pw_a)}"}
    client.post(DOMAINS_URL, json={"hostname": "a.example.com"}, headers=headers_a)

    user_b, pw_b = signup(client, email="ownerB@example.com")
    headers_b = {"Authorization": f"Bearer {login(client, user_b['email'], pw_b)}"}
    client.post(DOMAINS_URL, json={"hostname": "b.example.com"}, headers=headers_b)

    resp = client.get(DOMAINS_URL, headers=headers_a)
    hostnames = [d["hostname"] for d in resp.json()]
    assert hostnames == ["a.example.com"]


def test_verify_domain_succeeds_when_dns_txt_matches(auth_client, monkeypatch):
    client, headers, _ = auth_client
    domain = client.post(
        DOMAINS_URL, json={"hostname": "verifyme.example.com"}, headers=headers
    ).json()

    monkeypatch.setattr("app.api.routes.domains.check_dns_txt", lambda hostname, token: True)

    resp = client.post(f"{DOMAINS_URL}/{domain['id']}/verify", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["verified"] is True


def test_verify_domain_fails_when_dns_txt_missing(auth_client, monkeypatch):
    client, headers, _ = auth_client
    domain = client.post(
        DOMAINS_URL, json={"hostname": "notyet.example.com"}, headers=headers
    ).json()

    monkeypatch.setattr("app.api.routes.domains.check_dns_txt", lambda hostname, token: False)

    resp = client.post(f"{DOMAINS_URL}/{domain['id']}/verify", headers=headers)
    assert resp.status_code == 400
    assert domain["verified"] is False


def test_verify_domain_not_owned_by_caller_is_404(client):
    from tests.conftest import login, signup

    user_a, pw_a = signup(client, email="own1@example.com")
    headers_a = {"Authorization": f"Bearer {login(client, user_a['email'], pw_a)}"}
    domain = client.post(
        DOMAINS_URL, json={"hostname": "private.example.com"}, headers=headers_a
    ).json()

    user_b, pw_b = signup(client, email="own2@example.com")
    headers_b = {"Authorization": f"Bearer {login(client, user_b['email'], pw_b)}"}
    resp = client.post(f"{DOMAINS_URL}/{domain['id']}/verify", headers=headers_b)
    assert resp.status_code == 404


def test_set_and_clear_auth_cookie_never_echoes_value(auth_client):
    client, headers, _ = auth_client
    domain = client.post(
        DOMAINS_URL, json={"hostname": "cookietest.example.com"}, headers=headers
    ).json()

    resp = client.put(
        f"{DOMAINS_URL}/{domain['id']}/auth-cookie",
        json={"auth_cookie": "sessionid=super-secret"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["has_auth_cookie"] is True
    assert "sessionid" not in resp.text

    resp = client.put(f"{DOMAINS_URL}/{domain['id']}/auth-cookie", json={}, headers=headers)
    assert resp.json()["has_auth_cookie"] is False
