from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.result import TestResult, TestRun


def get_run(db: Session, run_id: int) -> TestRun:
    run = db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="测试任务不存在")
    return run


def list_runs(
    db: Session,
    *,
    status: str | None = None,
    interface_id: int | None = None,
    suite_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[int, list[TestRun]]:
    query = db.query(TestRun)
    if status:
        query = query.filter(TestRun.status == status)
    if interface_id is not None:
        query = query.filter(TestRun.interface_id == interface_id)
    if suite_id is not None:
        query = query.filter(TestRun.suite_id == suite_id)
    total = query.count()
    return total, query.order_by(TestRun.id.desc()).offset(offset).limit(limit).all()


def list_results(
    db: Session,
    run_id: int,
    *,
    status: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> tuple[int, list[TestResult]]:
    get_run(db, run_id)
    query = db.query(TestResult).filter(TestResult.run_id == run_id)
    if status:
        query = query.filter(TestResult.status == status)
    total = query.count()
    return total, query.order_by(TestResult.id.asc()).offset(offset).limit(limit).all()


def get_result(db: Session, result_id: int) -> TestResult:
    item = db.get(TestResult, result_id)
    if not item:
        raise HTTPException(status_code=404, detail="测试结果不存在")
    return item
