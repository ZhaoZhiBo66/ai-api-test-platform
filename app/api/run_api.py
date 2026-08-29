from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.api.security import require_api_key
from app.schemas.testcase_schema import RunRequest
from app.schemas.result_schema import AsyncRunAccepted, TestRunOut
from app.services.async_run_service import cancel_run, create_async_run
from app.services.test_runner import run_cases

router = APIRouter(prefix="/runs", tags=["测试执行"], dependencies=[Depends(require_api_key)])


@router.post("")
def run_test_cases(payload: RunRequest, db: Session = Depends(get_db)):
    run = run_cases(
        db=db,
        interface_id=payload.interface_id,
        case_ids=payload.case_ids,
        analyze_by_ai=payload.analyze_by_ai,
        environment_id=payload.environment_id,
        variables=payload.variables,
        fail_fast=payload.fail_fast,
    )
    return {
        "run_id": run.id,
        "status": run.status,
        "total": run.total,
        "passed": run.passed,
        "failed": run.failed,
        "ai_summary": run.ai_summary,
    }


@router.post("/async", response_model=AsyncRunAccepted, status_code=status.HTTP_202_ACCEPTED)
def run_test_cases_async(payload: RunRequest, db: Session = Depends(get_db)):
    run = create_async_run(db, payload)
    return {"run_id": run.id, "status": run.status}


@router.post("/{run_id}/cancel", response_model=TestRunOut)
def cancel_test_run(run_id: int, db: Session = Depends(get_db)):
    return cancel_run(db, run_id)

