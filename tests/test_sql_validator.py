import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.db import Base
from app.models.interface import ApiInterface
from app.services.sql_validator import SQLValidator


@pytest.fixture
def validator() -> SQLValidator:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(ApiInterface(name="登录接口", url="https://api.example.com/login", method="POST"))
    session.commit()
    session.close()

    instance = SQLValidator()
    # __init__ binds to settings.database_url; swap in the throwaway database so
    # a destructive statement that slips through cannot reach anything real.
    instance.engine.dispose()
    instance.engine = engine
    try:
        yield instance
    finally:
        engine.dispose()


def test_missing_sql_check_is_skipped(validator):
    assert validator.validate({}) == (True, "未配置 SQL 校验")


def test_missing_sql_key_is_skipped(validator):
    assert validator.validate({"expected": []}) == (True, "未配置 SQL 语句")


def test_select_without_expected_reports_row_count(validator):
    ok, message = validator.validate({"sql": "SELECT name FROM api_interfaces"})

    assert ok is True
    assert "1" in message


def test_select_matching_expected_dict_passes(validator):
    ok, message = validator.validate(
        {"sql": "SELECT name FROM api_interfaces", "expected": {"name": "登录接口"}}
    )

    assert (ok, message) == (True, "SQL校验通过")


def test_select_missing_expected_dict_fails(validator):
    ok, message = validator.validate(
        {"sql": "SELECT name FROM api_interfaces", "expected": {"name": "不存在的接口"}}
    )

    assert ok is False
    assert "SQL校验失败" in message


def test_select_matching_expected_list_passes(validator):
    ok, _ = validator.validate(
        {"sql": "SELECT name FROM api_interfaces", "expected": [{"name": "登录接口"}]}
    )

    assert ok is True


@pytest.mark.parametrize(
    "sql, reason",
    [
        ("DROP TABLE api_interfaces", "SQL校验只允许 SELECT 语句"),
        ("TRUNCATE TABLE api_interfaces", "SQL校验只允许 SELECT 语句"),
        ("DELETE FROM api_interfaces", "SQL校验只允许 SELECT 语句"),
        ("UPDATE api_interfaces SET name = 'x'", "SQL校验只允许 SELECT 语句"),
        ("INSERT INTO api_interfaces (name) VALUES ('x')", "SQL校验只允许 SELECT 语句"),
        ("ALTER TABLE api_interfaces ADD COLUMN x INT", "SQL校验只允许 SELECT 语句"),
        ("/* hide */ DROP TABLE api_interfaces", "SQL校验只允许 SELECT 语句"),
        ("SELECT 1; DROP TABLE api_interfaces", "SQL校验不允许多条语句"),
        ("   ", "SQL校验语句为空"),
        (";", "SQL校验语句为空"),
    ],
    ids=[
        "drop",
        "truncate",
        "delete",
        "update",
        "insert",
        "alter",
        "comment-prefixed-drop",
        "stacked-statements",
        "whitespace-only",
        "semicolon-only",
    ],
)
def test_non_select_statements_are_rejected(validator, sql, reason):
    assert validator.validate({"sql": sql}) == (False, reason)


def test_drop_table_leaves_the_table_intact(validator):
    """The reason the rejection exists: DDL used to execute and persist.

    Asserting the return value alone would pass even without the guard, since a
    DROP also returned False once fetchall() failed on it.
    """
    validator.validate({"sql": "DROP TABLE api_interfaces"})

    assert "api_interfaces" in inspect(validator.engine).get_table_names()


def test_delete_leaves_the_rows_intact(validator):
    validator.validate({"sql": "DELETE FROM api_interfaces"})

    ok, message = validator.validate({"sql": "SELECT name FROM api_interfaces"})
    assert (ok, "1" in message) == (True, True)


def test_trailing_semicolon_is_allowed(validator):
    ok, _ = validator.validate({"sql": "SELECT name FROM api_interfaces;"})

    assert ok is True


def test_lowercase_select_is_allowed(validator):
    ok, _ = validator.validate({"sql": "select name from api_interfaces"})

    assert ok is True


def test_broken_select_is_reported_not_raised(validator):
    ok, message = validator.validate({"sql": "SELECT nope FROM api_interfaces"})

    assert ok is False
    assert "SQL校验执行失败" in message
