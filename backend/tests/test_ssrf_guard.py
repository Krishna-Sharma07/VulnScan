from types import SimpleNamespace

import dns.resolver
import pytest

from app.services.ssrf_guard import (
    UnsafeScanTargetError,
    _is_public_ip,
    assert_public_scan_target,
    resolve_ips,
    resolve_pinned_ip,
)


# ---------------------------------------------------------------------------
# _is_public_ip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ip",
    [
        "10.0.0.1",  # RFC1918 private
        "192.168.1.1",  # RFC1918 private
        "172.16.0.5",  # RFC1918 private
        "127.0.0.1",  # loopback
        "169.254.169.254",  # link-local - the classic cloud metadata endpoint
        "224.0.0.1",  # multicast
        "0.0.0.0",  # unspecified
        "::1",  # IPv6 loopback
        "fe80::1",  # IPv6 link-local
        "fc00::1",  # IPv6 unique local (private)
        "::ffff:127.0.0.1",  # IPv4-mapped IPv6 loopback - a known filter-bypass trick
        "::ffff:10.0.0.1",  # IPv4-mapped IPv6 private
    ],
)
def test_is_public_ip_rejects_private_and_special_ranges(ip):
    assert _is_public_ip(ip) is False


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:4700:4700::1111"])
def test_is_public_ip_accepts_real_public_addresses(ip):
    assert _is_public_ip(ip) is True


# ---------------------------------------------------------------------------
# resolve_ips - dns.resolver.resolve is monkeypatched so no real network
# call happens; a fake rdata object only needs an `.address` attribute to
# match what resolve_ips actually reads off dnspython's real answers.
# ---------------------------------------------------------------------------


def _fake_rdata(address):
    return SimpleNamespace(address=address)


def _stub_resolve(monkeypatch, answers: dict):
    """answers: {"A": [...] | Exception, "AAAA": [...] | Exception}"""

    def _resolve(hostname, rdtype):
        result = answers.get(rdtype, dns.resolver.NoAnswer())
        if isinstance(result, Exception):
            raise result
        return [_fake_rdata(ip) for ip in result]

    monkeypatch.setattr("app.services.ssrf_guard.dns.resolver.resolve", _resolve)


def test_resolve_ips_combines_a_and_aaaa_records(monkeypatch):
    _stub_resolve(monkeypatch, {"A": ["8.8.8.8"], "AAAA": ["2606:4700:4700::1111"]})

    assert resolve_ips("example.com") == ["2606:4700:4700::1111", "8.8.8.8"]


def test_resolve_ips_returns_empty_when_nothing_resolves(monkeypatch):
    _stub_resolve(monkeypatch, {"A": dns.resolver.NXDOMAIN(), "AAAA": dns.resolver.NXDOMAIN()})

    assert resolve_ips("nowhere.invalid") == []


def test_resolve_ips_tolerates_one_record_type_missing(monkeypatch):
    _stub_resolve(monkeypatch, {"A": ["8.8.8.8"], "AAAA": dns.resolver.NoAnswer()})

    assert resolve_ips("ipv4-only.example.com") == ["8.8.8.8"]


# ---------------------------------------------------------------------------
# assert_public_scan_target - the guard actually called by scans.py/scanner.py
# ---------------------------------------------------------------------------


def test_assert_public_scan_target_allows_a_public_hostname(monkeypatch):
    _stub_resolve(monkeypatch, {"A": ["93.184.216.34"], "AAAA": dns.resolver.NoAnswer()})

    assert_public_scan_target("example.com")  # must not raise


def test_assert_public_scan_target_rejects_a_hostname_resolving_internally(monkeypatch):
    _stub_resolve(monkeypatch, {"A": ["127.0.0.1"], "AAAA": dns.resolver.NoAnswer()})

    with pytest.raises(UnsafeScanTargetError, match="127.0.0.1"):
        assert_public_scan_target("rebound.example.com")


def test_assert_public_scan_target_rejects_if_any_resolved_ip_is_unsafe(monkeypatch):
    # A domain can have multiple A records - one public, one pointed
    # internally is enough to make it an unsafe target.
    _stub_resolve(monkeypatch, {"A": ["93.184.216.34", "10.0.0.5"], "AAAA": dns.resolver.NoAnswer()})

    with pytest.raises(UnsafeScanTargetError, match="10.0.0.5"):
        assert_public_scan_target("mixed.example.com")


def test_assert_public_scan_target_rejects_unresolvable_hostname(monkeypatch):
    _stub_resolve(monkeypatch, {"A": dns.resolver.NXDOMAIN(), "AAAA": dns.resolver.NXDOMAIN()})

    with pytest.raises(UnsafeScanTargetError, match="Could not resolve"):
        assert_public_scan_target("nowhere.invalid")


def test_assert_public_scan_target_handles_a_public_ip_literal_without_dns(monkeypatch):
    def _unexpected_resolve(hostname, rdtype):
        raise AssertionError("should not perform a DNS lookup for an IP literal")

    monkeypatch.setattr("app.services.ssrf_guard.dns.resolver.resolve", _unexpected_resolve)

    assert_public_scan_target("8.8.8.8")  # must not raise, must not touch DNS


def test_assert_public_scan_target_rejects_a_private_ip_literal_without_dns(monkeypatch):
    def _unexpected_resolve(hostname, rdtype):
        raise AssertionError("should not perform a DNS lookup for an IP literal")

    monkeypatch.setattr("app.services.ssrf_guard.dns.resolver.resolve", _unexpected_resolve)

    with pytest.raises(UnsafeScanTargetError):
        assert_public_scan_target("169.254.169.254")


# ---------------------------------------------------------------------------
# resolve_pinned_ip - what scanner.py actually calls, since it needs the IP
# itself (to pin a scanner container's DNS to), not just a yes/no answer.
# ---------------------------------------------------------------------------


def test_resolve_pinned_ip_returns_the_resolved_address_for_a_safe_hostname(monkeypatch):
    _stub_resolve(monkeypatch, {"A": ["93.184.216.34"], "AAAA": dns.resolver.NoAnswer()})

    assert resolve_pinned_ip("example.com") == "93.184.216.34"


def test_resolve_pinned_ip_is_deterministic_when_a_hostname_has_several_addresses(monkeypatch):
    # resolve_ips returns addresses sorted - resolve_pinned_ip should commit
    # to that same, stable first address rather than picking arbitrarily.
    _stub_resolve(monkeypatch, {"A": ["93.184.216.34", "8.8.8.8"], "AAAA": dns.resolver.NoAnswer()})

    assert resolve_pinned_ip("multi.example.com") == "8.8.8.8"  # sorts before 93.184...


def test_resolve_pinned_ip_raises_for_an_unsafe_hostname(monkeypatch):
    _stub_resolve(monkeypatch, {"A": ["127.0.0.1"], "AAAA": dns.resolver.NoAnswer()})

    with pytest.raises(UnsafeScanTargetError):
        resolve_pinned_ip("rebound.example.com")


def test_resolve_pinned_ip_returns_a_public_ip_literal_unchanged_without_dns(monkeypatch):
    def _unexpected_resolve(hostname, rdtype):
        raise AssertionError("should not perform a DNS lookup for an IP literal")

    monkeypatch.setattr("app.services.ssrf_guard.dns.resolver.resolve", _unexpected_resolve)

    assert resolve_pinned_ip("8.8.8.8") == "8.8.8.8"


def test_resolve_pinned_ip_rejects_a_private_ip_literal_without_dns(monkeypatch):
    def _unexpected_resolve(hostname, rdtype):
        raise AssertionError("should not perform a DNS lookup for an IP literal")

    monkeypatch.setattr("app.services.ssrf_guard.dns.resolver.resolve", _unexpected_resolve)

    with pytest.raises(UnsafeScanTargetError):
        resolve_pinned_ip("10.0.0.5")
