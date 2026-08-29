from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


SENSITIVE_KEYWORDS = (
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "password",
    "passwd",
    "secret",
    "cookie",
)


def is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(keyword in normalized for keyword in SENSITIVE_KEYWORDS)


def redact(value: Any, *, max_string_length: int = 2000, max_items: int = 100) -> Any:
    """Return a log/model-safe copy without mutating the original value."""
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                result["__truncated__"] = f"remaining fields omitted after {max_items} items"
                break
            key_text = str(key)
            result[key_text] = "***REDACTED***" if is_sensitive_key(key_text) else redact(
                item, max_string_length=max_string_length, max_items=max_items
            )
        return result

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = list(value)
        safe = [redact(item, max_string_length=max_string_length, max_items=max_items) for item in items[:max_items]]
        if len(items) > max_items:
            safe.append(f"... {len(items) - max_items} more items omitted")
        return safe

    if isinstance(value, str) and len(value) > max_string_length:
        return value[:max_string_length] + f"... ({len(value) - max_string_length} chars omitted)"
    return value
