from src.flow.engine.redactor import Redactor


def test_redact_secrets():
    redactor = Redactor()
    secret = "sk-1234567890abcdef12345678"
    input_text = f"My key is {secret}"

    assert redactor.redact(input_text) == "My key is [REDACTED]"


def test_redact_github_token():
    redactor = Redactor()
    token = "ghp-1234567890abcdef12345678"
    input_text = f"Token: {token}"

    assert redactor.redact(input_text) == "Token: [REDACTED]"


def test_redact_safe_text():
    redactor = Redactor()
    text = "Hello world"
    assert redactor.redact(text) == text
