from typing import Tuple, Optional
from app.core.logging import logger


def normalize_email(email: str) -> str:
    """
    Normalizes an email address by trimming whitespace and converting to lowercase.
    """
    if not email:
        return ""
    return email.strip().lower()


def calculate_bounce_rate(leads_count: Optional[int] = None, bounced: int = 0, sent: Optional[int] = None) -> float:
    """
    Calculates bounce rate as a percentage rounded to 2 decimal places:
    bounce_rate = (bounce_count / leads_count) * 100

    If sent is passed or leads_count is None, uses sent as fallback for denominator.

    Validations:
    - denominator >= 0
    - bounced >= 0
    - If denominator == 0, returns 0.0
    - Logs warning if bounced > denominator (anomalous data from upstream provider)
    """
    denominator = leads_count if leads_count is not None else (sent if sent is not None else 0)

    if denominator < 0:
        logger.warning(f"Validation failure: denominator count cannot be negative ({denominator}). Treating as 0.")
        denominator = 0

    if bounced < 0:
        logger.warning(f"Validation failure: bounced count cannot be negative ({bounced}). Treating as 0.")
        bounced = 0

    if denominator == 0:
        if bounced > 0:
            logger.warning(f"Data anomaly: denominator=0 but bounced={bounced}. Bounce rate set to 0.0.")
        return 0.0

    if bounced > denominator:
        logger.warning(
            f"Data anomaly detected from upstream provider: bounced ({bounced}) exceeds leads/sent ({denominator}). "
            f"Calculating uncapped rate and logging warning."
        )

    rate = (bounced / denominator) * 100.0
    return round(rate, 2)


_MIMECAST_DOMAIN_CACHE: dict = {}


def is_mimecast_domain(domain: str, cache: Optional[dict] = None) -> bool:
    """
    Checks whether a recipient domain's DNS MX record points to Mimecast.
    Hostnames contain 'mimecast.com' or 'mimecast-'.
    Uses an in-memory cache to guarantee fast lookups with zero redundant DNS queries.
    """
    if not domain:
        return False
    clean_domain = domain.strip().lower()

    active_cache = cache if cache is not None else _MIMECAST_DOMAIN_CACHE
    if clean_domain in active_cache:
        return active_cache[clean_domain]

    try:
        import dns.resolver
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5.0
        resolver.lifetime = 6.0
        answers = resolver.resolve(clean_domain, "MX")
        is_mime = False
        for rdata in answers:
            host = str(rdata.exchange).lower().rstrip('.')
            if "mimecast.com" in host or "mimecast-" in host:
                is_mime = True
                break
        active_cache[clean_domain] = is_mime
        return is_mime
    except Exception:
        active_cache[clean_domain] = False
        return False

