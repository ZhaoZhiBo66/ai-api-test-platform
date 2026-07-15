from sqlalchemy import create_engine, text

from app.utils.config import get_settings
from app.utils.logger import logger


class SQLValidator:
    def __init__(self) -> None:
        self.engine = create_engine(get_settings().database_url, pool_pre_ping=True)

    def validate(self, sql_check: dict) -> tuple[bool, str]:
        if not sql_check:
            return True, "未配置 SQL 校验"

        sql = sql_check.get("sql")
        expected = sql_check.get("expected")
        if not sql:
            return True, "未配置 SQL 语句"

        try:
            with self.engine.connect() as conn:
                rows = [dict(row._mapping) for row in conn.execute(text(sql)).fetchall()]
        except Exception as exc:
            logger.exception("SQL校验执行失败")
            return False, f"SQL校验执行失败: {exc}"

        if expected is None:
            return True, f"SQL执行成功，返回 {len(rows)} 行"

        ok = expected in rows if isinstance(expected, dict) else rows == expected
        message = "SQL校验通过" if ok else f"SQL校验失败，实际结果: {rows}"
        return ok, message


sql_validator = SQLValidator()

