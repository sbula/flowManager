import re
from typing import List, Pattern


class Redactor:
    """
    Stream sanitizer for redaction of secrets and sensitive data.
    """
    DEFAULT_PATTERNS = [
        r"sk-[a-zA-Z0-9]{20,}",           # OpenAI Keys
        r"ghp-[a-zA-Z0-9]{20,}",          # GitHub Tokens
        r"Content-Type:.*",               # HTTP Headers (noise)
        r"Authorization: Bearer .*",      # Auth Headers
        r"password\s*=\s*['\"].*?['\"]",  # Config passwords
    ]

    def __init__(self, additional_patterns: List[str] = None):
        self._patterns: List[Pattern] = [
            re.compile(p) for p in self.DEFAULT_PATTERNS
        ]
        if additional_patterns:
            self._patterns.extend([re.compile(p) for p in additional_patterns])

    def redact(self, text: str) -> str:
        """
        Redact sensitive information from text.
        """
        if not text:
            return text

        redacted = text
        for pattern in self._patterns:
            redacted = pattern.sub("[REDACTED]", redacted)

        return redacted

    # Entropy check could be added here for advanced security
    # but strictly regex based for V1 speed.
