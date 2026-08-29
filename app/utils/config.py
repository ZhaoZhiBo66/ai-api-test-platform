import os
import json
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
        test_config = data.get("test", {})

        self.root_dir = ROOT_DIR
        self.app_name = app_config.get("name", "接口回归质量门禁平台")
        self.base_url = os.getenv("BASE_URL", app_config.get("base_url", "http://127.0.0.1:8000"))
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.api_auth_enabled = os.getenv(
            "API_AUTH_ENABLED", str(app_config.get("api_auth_enabled", False))
        ).lower() in {"1", "true", "yes", "on"}
        self.platform_api_key = os.getenv("PLATFORM_API_KEY", "")
        self.platform_encryption_key = os.getenv("PLATFORM_ENCRYPTION_KEY", "")
        raw_api_keys = os.getenv("PLATFORM_API_KEYS", "")
        try:
            self.platform_api_keys = json.loads(raw_api_keys) if raw_api_keys else {}
        except json.JSONDecodeError as exc:
            raise ValueError("PLATFORM_API_KEYS 必须是 JSON 对象") from exc

        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("OPENAI_MODEL", openai_config.get("model", "gpt-4o"))
        self.openai_temperature = float(openai_config.get("temperature", 0.2))
        self.openai_timeout = float(os.getenv("OPENAI_TIMEOUT", openai_config.get("timeout", 30)))
        self.openai_max_retries = int(os.getenv("OPENAI_MAX_RETRIES", openai_config.get("max_retries", 2)))
        self.openai_max_response_chars = int(
            os.getenv("OPENAI_MAX_RESPONSE_CHARS", openai_config.get("max_response_chars", 12000))
        )

        self.request_timeout = int(test_config.get("request_timeout", 10))
        self.allow_private_targets = os.getenv("ALLOW_PRIVATE_TARGETS", "false").lower() in {
            "1", "true", "yes", "on"
        }
        self.target_host_allowlist = {
            item.strip().lower()
            for item in os.getenv("TARGET_HOST_ALLOWLIST", "").split(",")
            if item.strip()
        }
        self.sut_allowed_tables = {
            item.strip().lower()
            for item in os.getenv("SUT_ALLOWED_TABLES", "").split(",")
            if item.strip()
        }
        self.max_sql_rows = int(test_config.get("max_sql_rows", 100))
        self.default_expected_status_code = int(test_config.get("default_expected_status_code", 200))

        self.async_workers = int(os.getenv("ASYNC_WORKERS", test_config.get("async_workers", 4)))
        self.max_queued_runs = int(os.getenv("MAX_QUEUED_RUNS", test_config.get("max_queued_runs", 100)))

        default_database = f"sqlite:///{(ROOT_DIR / 'ai_test_platform.db').as_posix()}"
        self.database_url = os.getenv("DATABASE_URL", default_database)

        # The database the SQL checks read, i.e. the one behind the API under
        # test. Deliberately not defaulting to database_url: that holds this
        # platform's own metadata tables, and checking those proves nothing.
        self.sut_database_url = os.getenv("SUT_DATABASE_URL", "")

@lru_cache
def get_settings() -> Settings:
    return Settings()

