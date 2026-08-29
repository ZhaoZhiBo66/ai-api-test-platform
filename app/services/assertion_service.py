from __future__ import annotations

import re
from typing import Any

from jsonschema import SchemaError, ValidationError, validate as validate_json_schema

from app.services.data_path import DataPathError, get_path


_MISSING = object()


def _actual_value(
    assertion: dict,
    *,
    status_code: int,
    body: Any,
    headers: dict[str, Any],
    duration_ms: int,
) -> Any:
    source = assertion.get("source", "body")
    if source == "status":
        return status_code
    if source == "duration_ms":
        return duration_ms
    if source == "body":
        return get_path(body, assertion.get("path", "$"), default=_MISSING)
    if source == "header":
        path = str(assertion.get("path", "")).lower()
        return {str(key).lower(): value for key, value in headers.items()}.get(path, _MISSING)
    raise ValueError(f"不支持的断言来源: {source}")


def _matches(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "exists":
        return actual is not _MISSING
    if operator == "not_exists":
        return actual is _MISSING
    if actual is _MISSING:
        return False
    if operator == "eq":
        return actual == expected
    if operator == "ne":
        return actual != expected
    if operator == "contains":
        return expected in actual
    if operator == "not_contains":
        return expected not in actual
    if operator == "gt":
        return actual > expected
    if operator == "gte":
        return actual >= expected
    if operator == "lt":
        return actual < expected
    if operator == "lte":
        return actual <= expected
    if operator == "in":
        return actual in expected
    if operator == "not_in":
        return actual not in expected
    if operator == "regex":
        return re.search(str(expected), str(actual)) is not None
    if operator == "type":
        types = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "object": dict, "array": list, "null": type(None)}
        expected_type = types.get(str(expected).lower())
        return expected_type is not None and isinstance(actual, expected_type)
    if operator == "length_eq":
        return len(actual) == expected
    if operator == "json_schema":
        validate_json_schema(instance=actual, schema=expected)
        return True
    raise ValueError(f"不支持的断言操作符: {operator}")


def evaluate_assertions(
    assertions: list[dict],
    *,
    status_code: int,
    body: Any,
    headers: dict[str, Any],
    duration_ms: int,
) -> list[str]:
    errors: list[str] = []
    for index, assertion in enumerate(assertions or [], start=1):
        operator = assertion.get("operator", "eq")
        expected = assertion.get("expected")
        try:
            actual = _actual_value(
                assertion,
                status_code=status_code,
                body=body,
                headers=headers,
                duration_ms=duration_ms,
            )
            if not _matches(actual, operator, expected):
                display_actual = "<不存在>" if actual is _MISSING else actual
                errors.append(
                    f"断言{index}失败: {assertion.get('source', 'body')} "
                    f"{assertion.get('path', '')} {operator} {expected!r}，实际 {display_actual!r}"
                )
        except (DataPathError, TypeError, ValueError, re.error, SchemaError, ValidationError) as exc:
            errors.append(f"断言{index}配置或执行错误: {exc}")
    return errors
