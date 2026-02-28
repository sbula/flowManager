import logging
import math
import os
import re
from typing import Dict, Optional, Set


class StreamRedactor:
    """
    Sanitizes output streams by removing secrets, high-entropy strings,
    and sensitive environment variables.
    """

    # Pre-compiled patterns for common secrets
    # sk-..., ghp-..., etc.
    SECRET_PATTERNS = [
        re.compile(r"(sk-[a-zA-Z0-9]{20,})"),  # OpenAI-style
        re.compile(r"(ghp_[a-zA-Z0-9]{30,})"),  # GitHub Personal Access Token
        re.compile(r"(xox[baprs]-[a-zA-Z0-9]{10,})"),  # Slack
        re.compile(
            r"([a-zA-Z0-9]{20,40}\.[a-zA-Z0-9]{20,40}\.[a-zA-Z0-9]{20,40})"
        ),  # JWT-like
        re.compile(r"(--BEGIN [A-Z]+ PRIVATE KEY--)"),  # PEM Headers
    ]

    def __init__(self, entropy_threshold: float = 4.5, min_len: int = 15):
        self.entropy_threshold = entropy_threshold
        self.min_len = min_len
        self.deny_list: Set[str] = set()
        self._load_env_secrets()

    def _load_env_secrets(self):
        """Loads values from os.environ that look sensitive."""
        block_keys = {
            "KEY",
            "SECRET",
            "TOKEN",
            "PASSWORD",
            "PASS",
            "AUTH",
            "CREDENTIAL",
        }
        for key, value in os.environ.items():
            if len(value) < 6:
                continue
            # If key contains any block word
            if any(bk in key.upper() for bk in block_keys):
                self.deny_list.add(value)

    def redact(self, content: str) -> str:
        """Applies all redaction layers."""
        if not content:
            return content

        redacted = content

        # 1. Known Environment Secrets
        for secret in self.deny_list:
            if secret in redacted:
                redacted = redacted.replace(secret, "[REDACTED_ENV]")

        # 2. Regex Patterns
        for pattern in self.SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED_PATTERN]", redacted)

        # 3. Entropy Scan (Word by word)
        # We split by whitespace to avoid flagging long sentences
        words = redacted.split()
        for word in words:
            # Clean punctuation for analysis
            clean_word = word.strip(".,;:'\"()[]{}")
            if len(clean_word) > self.min_len:
                if self._shannon_entropy(clean_word) > self.entropy_threshold:
                    # Replace the original word in the text
                    # Be careful with replace() matching substrings; strict token replacement is harder
                    # For now, simplistic replace (might over-redact duplicates)
                    redacted = redacted.replace(clean_word, "[REDACTED_ENTROPY]")

        return redacted

    def _shannon_entropy(self, data: str) -> float:
        """Calculates Shannon entropy of a string."""
        if not data:
            return 0
        entropy = 0.0
        length = len(data)

        # Count frequencies
        freqs: Dict[str, int] = {}
        for char in data:
            freqs[char] = freqs.get(char, 0) + 1

        for count in freqs.values():
            p = count / length
            entropy -= p * math.log2(p)

        return entropy
