import pytest
import os
from unittest.mock import patch
from src.flow.security.redactor import StreamRedactor

@pytest.fixture
def redactor():
    with patch.dict(os.environ, {"MY_SECRET_KEY": "super_secret_value_123"}):
        return StreamRedactor()

def test_redact_environment_variable(redactor):
    """Verify values from os.environ are redacted."""
    # Redactor loads env on init, so we need to mock internal load or init
    # The fixture patched os.environ, but we need to ensure redactor loaded it.
    # Let's re-instantiate inside test or trust fixture if it works.
    # Actually, os.environ patch in fixture works if instantiated there.
    
    input_text = "The secret is super_secret_value_123."
    output = redactor.redact(input_text)
    assert "[REDACTED_ENV]" in output
    assert "super_secret_value_123" not in output

def test_redact_known_pattern():
    """Verify sk- keys are redacted."""
    redactor = StreamRedactor()
    input_text = "Key: sk-1234567890abcdef1234567890abcdef"
    output = redactor.redact(input_text)
    assert "[REDACTED_PATTERN]" in output
    assert "sk-12345" not in output

def test_redact_high_entropy():
    """Verify high entropy strings are redacted."""
    redactor = StreamRedactor()
    # A random 32-char string
    high_entropy = "8f9d2a3B7c1E6g5H4i0Jk9L8m7N6o5P4" 
    input_text = f"Token: {high_entropy}"
    output = redactor.redact(input_text)
    assert "[REDACTED_ENTROPY]" in output or "[REDACTED_PATTERN]" in output

def test_allow_low_entropy():
    """Verify normal text is NOT redacted."""
    redactor = StreamRedactor()
    input_text = "This is a normal sentence with low entropy words."
    output = redactor.redact(input_text)
    assert output == input_text

def test_short_values_ignored():
    """Verify short environment variables don't cause false positives."""
    with patch.dict(os.environ, {"SHORT_KEY": "12345"}):
        redactor = StreamRedactor()
        input_text = "Count 12345 items."
        output = redactor.redact(input_text)
        assert "12345" in output  # length < 6 ignored by default
