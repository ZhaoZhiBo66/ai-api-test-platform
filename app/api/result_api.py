from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.security import require_api_key
from app.database.db import get_db
from app.schemas.result_schema import ResultPage, RunPage, TestResultOut, TestRunOut
from app.services import result_service


router = APIRouter(tags=["测试结果"], dependencies=[Depends(require_api_key)])


@router.get("/runs", response_model=RunPage)
def list_runs(
    status: str | None = Query(default=None),
    interface_id: int | None = Query(default=None),
    suite_id: int | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    total, items = result_service.list_runs(
        db,
        status=status,
        interface_id=interface_id,
        suite_id=suite_id,
        offset=offset,
        limit=limit,
    )
    return {"total": total, "offset": offset, "limit": limit, "items": items}


@router.get("/runs/{run_id}", response_model=TestRunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    return result_service.get_run(db, run_id)


@router.get("/runs/{run_id}/results", response_model=ResultPage)
def list_run_results(
    run_id: int,
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    total, items = result_service.list_results(
        db, run_id, status=status, offset=offset, limit=limit
    )
    return {"total": total, "offset": offset, "limit": limit, "items": items}


@router.get("/results/{result_id}", response_model=TestResultOut)
def get_result(result_id: int, db: Session = Depends(get_db)):
    return result_service.get_result(db, result_id)
