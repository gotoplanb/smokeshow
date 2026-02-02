"""Sensitive data redaction for form field values."""

import re

_SENSITIVE_PATTERNS = re.compile(
    r"(password|passwd|card|cvv|ssn|credit|secret|token)", re.IGNORECASE
)

REDACTED = "[REDACTED]"


def is_sensitive_selector(selector: str) -> bool:
    """Check if a CSS selector references a sensitive field."""
    return bool(_SENSITIVE_PATTERNS.search(selector))


def redact_if_needed(value: str, selector: str, sensitive: bool = False) -> str:
    """Return REDACTED if the field is sensitive, otherwise the original value."""
    if sensitive or is_sensitive_selector(selector):
        return REDACTED
    return value
