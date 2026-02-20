"""
Input Validation & Sanitization Utilities

Provides security-related validation helpers.
"""

import re
from typing import Optional

import bleach


def sanitize_html(text: str) -> str:
    """Strip all HTML tags from input text."""
    return bleach.clean(text, tags=[], strip=True)


def validate_password_strength(password: str) -> Optional[str]:
    """Validate password meets complexity requirements.

    Requirements:
        - Minimum 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character

    Returns:
        Error message if validation fails, None if valid.
    """
    if len(password) < 8:
        return "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return "Password must contain at least one digit"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return "Password must contain at least one special character"
    return None


# Patterns for PII detection
PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}


def detect_pii(text: str) -> dict[str, list[str]]:
    """Scan text for potential PII patterns.

    Returns:
        Dictionary mapping PII type to list of detected patterns.
    """
    findings: dict[str, list[str]] = {}
    for pii_type, pattern in PII_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            findings[pii_type] = matches
    return findings
