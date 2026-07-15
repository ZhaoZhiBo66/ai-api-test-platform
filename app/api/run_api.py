from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.schemas.testcase_schema import RunRequest
from app.services.test_runner import run_cases

router = APIRouter(prefix="/runs", tags=["测试执行"])


@router.post("")
def run_test_cases(payload: RunRequest, db: Session = Depends(get_db)):
    run = run_cases(
        db=db,
        interface_id=payload.interface_id,
        case_ids=payload.case_ids,
        analyze_by_ai=payload.analyze_by_ai,
    )
    return {
        "run_id": run.id,
        "status": run.status,
        "total": run.total,
        "passed": run.passed,
        "failed": run.failed,
        "ai_summary": run.ai_summary,
    }

