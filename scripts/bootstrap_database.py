"""Upgrade a new database or adopt the schema used before Alembic was added."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.utils.config import get_settings


def main() -> None:
    settings = get_settings()
    config = Config(settings.root_dir / "alembic.ini")
    engine = create_engine(settings.database_url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    baseline_tables = {"api_interfaces", "test_cases", "test_runs", "test_results"}
    if "alembic_version" not in tables and baseline_tables.issubset(tables):
        print("Existing pre-Alembic schema detected; stamping 0001_baseline.")
        command.stamp(config, "0001_baseline")
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
