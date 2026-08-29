import pytest

from app.services.assertion_service import evaluate_assertions
from app.services.data_path import DataPathError, get_path
from app.services.variable_service import extract_variables, render_value, resolve_url


def test_jsonpath_supports_nested_arrays_and_wildcards():
    body = {"data": {"users": [{"id": 1}, {"id": 2}]}}

    assert get_path(body, "$.data.users[1].id") == 2
    assert get_path(body, "$.data.users[*].id") == [1, 2]


def test_jsonpath_rejects_unsupported_or_missing_paths():
    with pytest.raises(DataPathError):
        get_path({}, "data.id")
    with pytest.raises(DataPathError):
        get_path({}, "$.data.id")


def test_render_value_preserves_full_variable_types_and_renders_nested_values():
    variables = {"token": "abc", "user_id": 7}

    rendered = render_value(
        {"Authorization": "Bearer ${token}", "ids": ["${user_id}"]},
        variables,
    )

    assert rendered == {"Authorization": "Bearer abc", "ids": [7]}


def test_render_value_reports_missing_variables():
    with pytest.raises(ValueError, match="变量未定义"):
        render_value("Bearer ${missing}", {})


def test_relative_url_requires_and_uses_environment_base_url():
    assert resolve_url("/v1/login", "https://api.example.com") == "https://api.example.com/v1/login"
    with pytest.raises(ValueError, match="base_url"):
        resolve_url("/v1/login")


def test_extract_variables_reads_jsonpath_and_headers():
    extracted = extract_variables(
        [
            {"name": "token", "source": "body", "path": "$.data.token"},
            {"name": "trace", "source": "header", "path": "X-Trace-Id"},
        ],
        body={"data": {"token": "secret"}},
        headers={"x-trace-id": "trace-1"},
        status_code=200,
    )

    assert extracted == {"token": "secret", "trace": "trace-1"}


def test_assertion_engine_supports_body_header_duration_and_regex():
    errors = evaluate_assertions(
        [
            {"source": "body", "path": "$.data.id", "operator": "eq", "expected": 7},
            {"source": "header", "path": "Content-Type", "operator": "contains", "expected": "json"},
            {"source": "duration_ms", "operator": "lt", "expected": 500},
            {"source": "body", "path": "$.data.email", "operator": "regex", "expected": r"@example\.com$"},
        ],
        status_code=200,
        body={"data": {"id": 7, "email": "qa@example.com"}},
        headers={"Content-Type": "application/json"},
        duration_ms=30,
    )

    assert errors == []


def test_assertion_engine_returns_readable_failures_instead_of_raising():
    errors = evaluate_assertions(
        [{"source": "body", "path": "$.missing", "operator": "eq", "expected": 1}],
        status_code=200,
        body={},
        headers={},
        duration_ms=0,
    )

    assert len(errors) == 1
    assert "断言1失败" in errors[0]


def test_assertion_engine_supports_json_schema_validation():
    assertions = [
        {
            "source": "body",
            "path": "$.data",
            "operator": "json_schema",
            "expected": {
                "type": "object",
                "required": ["id", "name"],
                "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
            },
        }
    ]

    assert evaluate_assertions(
        assertions,
        status_code=200,
        body={"data": {"id": 1, "name": "qa"}},
        headers={},
        duration_ms=1,
    ) == []
    errors = evaluate_assertions(
        assertions,
        status_code=200,
        body={"data": {"id": "wrong"}},
        headers={},
        duration_ms=1,
    )
    assert len(errors) == 1
    assert "断言1配置或执行错误" in errors[0]
