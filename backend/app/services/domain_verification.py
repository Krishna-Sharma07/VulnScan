import dns.resolver

from app.core.config import settings


def expected_txt_value(token: str) -> str:
    return f"{settings.verification_txt_prefix}={token}"


def check_dns_txt(hostname: str, token: str) -> bool:
    """Query the domain's TXT records and look for our verification value.
    This is how we confirm the person registering a scan target actually
    controls its DNS, before we let any scan run against it."""
    expected = expected_txt_value(token)
    try:
        answers = dns.resolver.resolve(hostname, "TXT")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return False

    for record in answers:
        # TXT records are returned as one or more quoted byte-strings; join them.
        value = b"".join(record.strings).decode("utf-8", errors="ignore")
        if value == expected:
            return True
    return False
