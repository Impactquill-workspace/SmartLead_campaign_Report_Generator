import re
from typing import Optional


def sanitize_sensitive_data(message: str, api_key: Optional[str] = None) -> str:
    """
    Sanitizes API keys, authorization tokens, passwords, and sensitive headers from log messages and strings.
    """
    if not message:
        return ""

    sanitized = str(message)

    # If explicit API key is provided, mask all occurrences
    if api_key and len(api_key.strip()) > 3:
        sanitized = sanitized.replace(api_key.strip(), "***REDACTED_API_KEY***")

    # Regex patterns for query params, headers, and json payloads
    patterns = [
        # Query parameter: ?api_key=xyz or &api_key=xyz
        (r"([?&]api_key=)[^&\s]+", r"\1***REDACTED***"),
        # Authorization header: Authorization: Bearer xyz or Token xyz
        (r"(Authorization[\"']?\s*[:=]\s*[\"']?(?:Bearer|Token)?\s*)([A-Za-z0-9\-_.+=/]+)", r"\1***REDACTED***"),
        # JSON fields: "api_key": "xyz" or "password": "xyz" or "token": "xyz"
        (r"([\"']?(?:api_key|apiKey|password|token|secret)[\"']?\s*[:=]\s*[\"'])([^\"',]+)([\"'])", r"\1***REDACTED***\3"),
    ]

    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    return sanitized
