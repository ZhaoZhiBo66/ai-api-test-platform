import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def _read_yaml() -> dict[str, Any]:
    config_path = ROOT_DIR / "config.yaml"
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


class Settings:
    def __init__(self) -> None:
        data = _read_yaml()
        app_config = data.get("app", {})
        openai_config = data.get("openai", {})
        db_config = data.get("database", {})
        test_config = data.get("test", {})

        self.root_dir = ROOT_DIR
        self.app_name = app_config.get("name", "AI 智能接口自动化测试平台")
        self.base_url = os.getenv("BASE_URL", app_config.get("base_url", "http://127.0.0.1:8000"))
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("OPENAI_MODEL", openai_config.get("model", "gpt-4o"))
        self.openai_temperature = float(openai_config.get("temperature", 0.2))

        self.request_timeout = int(test_config.get("request_timeout", 10))
        self.default_expected_status_code = int(test_config.get("default_expected_status_code", 200))

        self.database_url = os.getenv("DATABASE_URL", self._build_mysql_url(db_config))

        # The database the SQL checks read, i.e. the one behind the API under
        # test. Deliberately not defaulting to database_url: that holds this
        # platform's own metadata tables, and checking those proves nothing.
        self.sut_database_url = os.getenv("SUT_DATABASE_URL", "")

    @staticmethod
    def _build_mysql_url(db_config: dict[str, Any]) -> str:
        driver = db_config.get("driver", "mysql+pymysql")
        host = os.getenv("DB_HOST", db_config.get("host", "127.0.0.1"))
        port = os.getenv("DB_PORT", str(db_config.get("port", 3306)))
        user = os.getenv("DB_USER", db_config.get("user", "root"))
        password = os.getenv("DB_PASSWORD", db_config.get("password", "123456"))
        name = os.getenv("DB_NAME", db_config.get("name", "ai_test_platform"))
        return f"{driver}://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


@lru_cache
def get_settings() -> Settings:
    return Settings()

