"""
Input Validation & Sanitization Utilities

Provides security-related helpers:
  - HTML sanitization (bleach)
  - Password strength validation
  - PII pattern scanning
  - Prompt injection detection
  - Generic text sanitization for schema fields
"""

import re
from typing import Optional

import bleach


# --- HTML Sanitization ---


def sanitize_html(text: str) -> str:
    """Strip all HTML tags from input text."""
    return bleach.clean(text, tags=[], strip=True)


def sanitize_text(text: str) -> str:
    """Sanitize user-provided text: strip HTML and normalize whitespace."""
    cleaned = bleach.clean(text, tags=[], strip=True)
    # Collapse multiple whitespace lines but keep paragraph breaks
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def sanitize_optional(text: Optional[str]) -> Optional[str]:
    """Sanitize text if provided, otherwise return None."""
    if text is None:
        return None
    result = sanitize_text(text)
    return result if result else None


# --- Password Validation ---


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


# --- PII Detection ---


PII_PATTERNS = {
    "email": re.compile(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    ),
    "phone": re.compile(
        r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    ),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b"
    ),
}

# Placeholder patterns that are *allowed* (not real PII)
PII_SAFE_PLACEHOLDERS = re.compile(
    r"\[(?:TARGET_NAME|TARGET_EMAIL|COMPANY_EMAIL|COMPANY_NAME|DEPARTMENT|PHONE_NUMBER|EMPLOYEE_ID)\]",
    re.IGNORECASE,
)


def detect_pii(text: str) -> dict[str, list[str]]:
    """Scan text for potential PII patterns.

    Excludes matches inside safe placeholder brackets.

    Returns:
        Dictionary mapping PII type to list of detected patterns.
    """
    # Remove safe placeholders so they don't trigger false positives
    cleaned = PII_SAFE_PLACEHOLDERS.sub("", text)

    findings: dict[str, list[str]] = {}
    for pii_type, pattern in PII_PATTERNS.items():
        matches = pattern.findall(cleaned)
        if matches:
            findings[pii_type] = matches
    return findings


# --- Prompt Injection Detection ---


# Patterns indicating prompt injection / jailbreak attempts
_INJECTION_PATTERNS = [
    # Direct instruction override
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|rules|prompts)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|above|prior)\s+(instructions|rules)", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|above|prior)", re.IGNORECASE),
    # System prompt extraction
    re.compile(r"(print|show|reveal|output|display)\s+(your|the)\s+(system|initial)\s+(prompt|instructions)", re.IGNORECASE),
    re.compile(r"what\s+(are|is)\s+your\s+(system|initial)\s+(prompt|instructions)", re.IGNORECASE),
    # Role manipulation
    re.compile(r"you\s+are\s+now\s+(DAN|an?\s+unrestricted|jailbroken)", re.IGNORECASE),
    re.compile(r"enter\s+(DAN|developer|god)\s+mode", re.IGNORECASE),
    re.compile(r"act\s+as\s+if\s+you\s+have\s+no\s+(restrictions|limitations|rules)", re.IGNORECASE),
    # Encoding / obfuscation bypass
    re.compile(r"(base64|rot13|hex)\s*(encode|decode|translate)", re.IGNORECASE),
    re.compile(r"respond\s+in\s+(base64|binary|hex)", re.IGNORECASE),
    # Delimiter injection
    re.compile(r"```\s*(system|assistant|user)\s*", re.IGNORECASE),
    re.compile(r"<\|?(system|im_start|im_end)\|?>", re.IGNORECASE),
]


def detect_prompt_injection(text: str) -> list[str]:
    """Scan text for prompt injection / jailbreak patterns.

    Returns:
        List of detected injection pattern descriptions. Empty if clean.
    """
    findings: list[str] = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            findings.append(f"Matched pattern: {pattern.pattern[:60]}...")
    return findings
