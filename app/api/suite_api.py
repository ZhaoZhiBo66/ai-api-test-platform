from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.security import require_api_key
from app.database.db import get_db
from app.schemas.result_schema import AsyncRunAccepted
from app.schemas.suite_schema import (
    SuiteRunRequest,
    SuiteTrendOut,
    TestSuiteCreate,
    TestSuiteOut,
    TestSuiteUpdate,
)
from app.schemas.testcase_schema import RunRequest
from app.services import suite_service
from app.services.async_run_service import create_async_run
from app.services.test_runner import run_cases


router = APIRouter(prefix="/suites", tags=["回归套件"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=TestSuiteOut, status_code=status.HTTP_201_CREATED)
def create_suite(payload: TestSuiteCreate, db: Session = Depends(get_db)):
    return suite_service.create_suite(db, payload)


@router.get("", response_model=list[TestSuiteOut])
def list_suites(
    enabled: bool | None = Query(default=None), db: Session = Depends(get_db)
):
    return suite_service.list_suites(db, enabled=enabled)


@router.get("/{suite_id}", response_model=TestSuiteOut)
def get_suite(suite_id: int, db: Session = Depends(get_db)):
    return suite_service.get_suite(db, suite_id)


@router.put("/{suite_id}", response_model=TestSuiteOut)
def update_suite(suite_id: int, payload: TestSuiteUpdate, db: Session = Depends(get_db)):
    return suite_service.update_suite(db, suite_id, payload)


@router.delete("/{suite_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_suite(suite_id: int, db: Session = Depends(get_db)):
    suite_service.delete_suite(db, suite_id)


def _run_payload(db: Session, suite_id: int, payload: SuiteRunRequest) -> tuple[RunRequest, bool, bool]:
    suite, case_ids = suite_service.suite_case_ids(db, suite_id)
    fail_fast = suite.fail_fast if payload.fail_fast is None else payload.fail_fast
    analyze_by_ai = suite.analyze_by_ai if payload.analyze_by_ai is None else payload.analyze_by_ai
    return (
        RunRequest(
            case_ids=case_ids,
            environment_id=payload.environment_id,
            variables=payload.variables,
            fail_fast=fail_fast,
            analyze_by_ai=analyze_by_ai,
        ),
        fail_fast,
        analyze_by_ai,
    )


@router.post("/{suite_id}/runs")
def run_suite(suite_id: int, payload: SuiteRunRequest, db: Session = Depends(get_db)):
    run_payload, fail_fast, analyze_by_ai = _run_payload(db, suite_id, payload)
    run = run_cases(
        db,
        interface_id=None,
        case_ids=run_payload.case_ids,
        analyze_by_ai=analyze_by_ai,
        environment_id=run_payload.environment_id,
        variables=run_payload.variables,
        fail_fast=fail_fast,
        suite_id=suite_id,
    )
    return {
        "run_id": run.id,
        "status": run.status,
        "total": run.total,
        "passed": run.passed,
        "failed": run.failed,
    }


@router.post(
    "/{suite_id}/runs/async", response_model=AsyncRunAccepted, status_code=status.HTTP_202_ACCEPTED
)
def run_suite_async(suite_id: int, payload: SuiteRunRequest, db: Session = Depends(get_db)):
    run_payload, _, _ = _run_payload(db, suite_id, payload)
    run = create_async_run(db, run_payload, suite_id=suite_id)
    return {"run_id": run.id, "status": run.status}


@router.get("/{suite_id}/trends", response_model=SuiteTrendOut)
def suite_trends(
    suite_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return suite_service.suite_trends(db, suite_id, limit)
