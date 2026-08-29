from app.utils.redaction import redact


def test_redact_hides_nested_secrets_without_mutating_input():
    original = {
        "username": "admin",
        "password": "plain-text",
        "headers": {"Authorization": "Bearer secret", "X-Trace": "ok"},
    }

    safe = redact(original)

    assert safe["password"] == "***REDACTED***"
    assert safe["headers"]["Authorization"] == "***REDACTED***"
    assert safe["headers"]["X-Trace"] == "ok"
    assert original["password"] == "plain-text"


def test_redact_truncates_oversized_strings():
    assert "omitted" in redact("x" * 20, max_string_length=5)
