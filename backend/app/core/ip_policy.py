import ipaddress
import logging

logger = logging.getLogger(__name__)


def is_ip_allowed_in_workspace(client_ip: str, allowlist: list[str] | None) -> bool:
    """
    Validate whether client IP address is permitted by workspace CIDR allowlist.
    Returns True if allowlist is empty or unconfigured (open access).
    Returns False if client IP does not fall within any authorized network CIDR.
    """
    if not allowlist:
        return True

    cleaned_ip = (client_ip or "").strip()
    if not cleaned_ip:
        return False

    try:
        ip_obj = ipaddress.ip_address(cleaned_ip)
    except ValueError:
        logger.warning(f"Malformed client IP address: '{cleaned_ip}'")
        return False

    for rule in allowlist:
        r = rule.strip()
        if not r:
            continue
        try:
            # Check CIDR network subnet (e.g. "192.168.1.0/24", "10.0.0.0/8", "::1/128")
            net = ipaddress.ip_network(r, strict=False)
            if ip_obj in net:
                return True
        except ValueError:
            # Check individual literal IP match
            if str(ip_obj) == r:
                return True

    return False


def validate_cidr_rules(rules: list[str]) -> list[str]:
    """Validate that every rule in the list adheres to valid IP address or CIDR notation."""
    validated = []
    for r in rules:
        rule_str = r.strip()
        if not rule_str:
            continue
        try:
            ipaddress.ip_network(rule_str, strict=False)
            validated.append(rule_str)
        except ValueError:
            raise ValueError(f"Invalid IP address or CIDR network rule: '{rule_str}'")
    return validated
