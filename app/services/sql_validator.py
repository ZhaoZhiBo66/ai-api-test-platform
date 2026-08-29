import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.utils.config import get_settings
from app.utils.logger import logger

_SELECT_ONLY = re.compile(r"^select\s", re.IGNORECASE)
_DANGEROUS_SELECT = re.compile(
    r"\b(?:into\s+(?:out|dump)file|for\s+update|lock\s+in\s+share\s+mode)\b"
    r"|\b(?:load_file|sleep|benchmark)\s*\(",
    re.IGNORECASE,
)
_TABLE_REFERENCE = re.compile(r"\b(?:from|join)\s+[`\"]?([A-Za-z_][\w.]*)", re.IGNORECASE)


def _reject_reason(sql: str) -> str | None:
    """Return why `sql` is not an acceptable read-only check, or None if it is.

    sql_check comes straight from the API and reaches a live database.
    Statements are rejected rather than sanitised: a check that is not a plain
    SELECT is a mistake worth surfacing, not something to guess the intent of.
    """
    statement = sql.strip().rstrip(";").strip()
    if not statement:
        return "SQL校验语句为空"
    if ";" in statement:
        # Neither driver enables multi-statement execution by default, but a
        # payload that tries is never a legitimate check.
        return "SQL校验不允许多条语句"
    if not _SELECT_ONLY.match(statement):
        # A leading comment also lands here: harmless checks are rewritten
        # more easily than comment-hiding is detected reliably.
        return "SQL校验只允许 SELECT 语句"
    if _DANGEROUS_SELECT.search(statement):
        return "SQL校验包含高风险 SELECT 能力，已拒绝执行"
    allowlist = get_settings().sut_allowed_tables
    if allowlist:
        referenced = {match.lower().split(".")[-1] for match in _TABLE_REFERENCE.findall(statement)}
        denied = sorted(referenced - allowlist)
        if denied:
            return f"SQL校验访问了未授权表: {denied}"
    return None


class SQLValidator:
    def __init__(self) -> None:
        # Built on first use, not here: this class is instantiated at import
        # time, and SUT_DATABASE_URL may legitimately be unset.
        self.engine: Engine | None = None

    def _get_engine(self) -> Engine | None:
        if self.engine is None:
            url = get_settings().sut_database_url
            if not url:
                return None
            self.engine = create_engine(url, pool_pre_ping=True)
        return self.engine

    def validate(self, sql_check: dict) -> tuple[bool, str]:
        if not sql_check:
            return True, "未配置 SQL 校验"

        sql = sql_check.get("sql")
        expected = sql_check.get("expected")
        if not sql:
            return True, "未配置 SQL 语句"

        reason = _reject_reason(sql)
        if reason:
            logger.warning("拒绝执行 SQL 校验语句: {}", sql)
            return False, reason

        engine = self._get_engine()
        if engine is None:
            return False, "未配置被测系统数据库 SUT_DATABASE_URL，无法执行 SQL 校验"

        try:
            with engine.connect() as conn:
                max_rows = get_settings().max_sql_rows
                rows = [dict(row._mapping) for row in conn.execute(text(sql)).fetchmany(max_rows + 1)]
        except Exception as exc:
            logger.exception("SQL校验执行失败")
            return False, f"SQL校验执行失败: {exc}"

        if len(rows) > get_settings().max_sql_rows:
            return False, f"SQL校验结果超过 {get_settings().max_sql_rows} 行上限"

        if expected is None:
            return True, f"SQL执行成功，返回 {len(rows)} 行"

        ok = expected in rows if isinstance(expected, dict) else rows == expected
        message = "SQL校验通过" if ok else f"SQL校验失败，返回 {len(rows)} 行，结果与预期不符"
        return ok, message


sql_validator = SQLValidator()

