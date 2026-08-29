from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.security import require_api_key
from app.database.db import get_db
from app.models.environment import TestEnvironment
from app.models.interface import ApiInterface
from app.models.result import TestResult, TestRun
from app.models.suite import TestSuite
from app.models.testcase import TestCase


router = APIRouter(prefix="/system", tags=["系统信息"], dependencies=[Depends(require_api_key)])


@router.get("/info")
def system_info(db: Session = Depends(get_db)) -> dict:
    url = make_url(str(db.get_bind().url))
    backend = url.get_backend_name()
    database = url.database or "memory"
    if backend == "sqlite" and database not in {"memory", ":memory:"}:
        database = Path(database).name
    return {
        "storage": "SQLite" if backend == "sqlite" else backend.upper(),
        "database": database,
        "persistent": database not in {"memory", ":memory:"},
        "counts": {
            "environments": db.query(TestEnvironment).count(),
            "interfaces": db.query(ApiInterface).count(),
            "cases": db.query(TestCase).count(),
            "runs": db.query(TestRun).count(),
            "results": db.query(TestResult).count(),
            "suites": db.query(TestSuite).count(),
        },
    }
