import ipaddress

import dns.resolver


class UnsafeScanTargetError(Exception):
    """Raised when a scan target's hostname resolves to a non-public IP."""


def _is_public_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    # An IPv4-mapped IPv6 address (::ffff:127.0.0.1) would otherwise sail
    # through as "not private" - ipaddress only classifies the IPv6 form
    # itself, so unwrap it and classify the embedded IPv4 address instead.
    if addr.version == 6 and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def resolve_ips(hostname: str) -> list[str]:
    """Resolves hostname to every A/AAAA address it currently has."""
    ips: set[str] = set()
    for rdtype in ("A", "AAAA"):
        try:
            answers = dns.resolver.resolve(hostname, rdtype)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            continue
        for rdata in answers:
            ips.add(rdata.address)
    return sorted(ips)


def resolve_pinned_ip(hostname: str) -> str:
    """Resolves `hostname`, raising UnsafeScanTargetError unless every
    address it currently has is public, and returns one specific IP for
    callers to pin the rest of a scan to (see `assert_public_scan_target`
    and app/services/scanner.py's resolver-pinning note for why "one
    specific IP, reused for the whole scan" matters, not just "safe at the
    moment we checked"). If `hostname` is itself an IP literal, DNS is
    skipped entirely and that address is validated and returned directly.

    Picks the lexicographically-first address when a hostname has several
    (`resolve_ips` already returns them sorted) - deterministic rather than
    meaningful, since the point is just "one address we can commit to."
    """
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None

    if literal is not None:
        candidates = [str(literal)]
    else:
        candidates = resolve_ips(hostname)
        if not candidates:
            raise UnsafeScanTargetError(f"Could not resolve '{hostname}' to any IP address.")

    unsafe = [candidate for candidate in candidates if not _is_public_ip(candidate)]
    if unsafe:
        raise UnsafeScanTargetError(
            f"'{hostname}' resolves to a private/internal address ({', '.join(unsafe)}) "
            "and cannot be used as a scan target."
        )
    return candidates[0]


def assert_public_scan_target(hostname: str) -> None:
    """Raises UnsafeScanTargetError if `hostname` doesn't resolve to a public
    IP address - the SSRF guard for scan targets, for callers (the API
    layer) that only need a yes/no answer, not a pinned IP to launch a
    container against. See `resolve_pinned_ip` for the pinning variant
    scanner.py actually uses.

    Domain-ownership verification (app/services/domain_verification.py)
    proves the user controls a hostname's DNS. It does NOT prove that
    hostname's DNS points somewhere safe to aim a scanner container at - DNS
    is entirely attacker-controlled, so a verified domain's A/AAAA record
    could point at 127.0.0.1, a container on vulnscan-network, or (on real
    cloud infra) the cloud metadata endpoint. That's a classic SSRF-via-
    scanner pattern: "verify" a domain while it points somewhere public,
    then repoint its DNS before or during the scan.

    This alone only proves DNS was safe *at the moment this function ran* -
    it's called at scan creation for fast user feedback, but the call that
    actually matters is `resolve_pinned_ip` in app/services/scanner.py,
    right before a scanner container launches, whose result is then used to
    pin that container's own hostname resolution (via Docker `extra_hosts`)
    for its entire run - closing both the "queued, then DNS changed before
    the worker picked it up" window and mid-scan DNS rebinding, since the
    container never performs a fresh DNS lookup for the target at all once
    pinned.
    """
    resolve_pinned_ip(hostname)
