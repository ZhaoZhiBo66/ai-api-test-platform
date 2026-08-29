from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.result import TestRun
from app.models.suite import TestSuite, TestSuiteCase
from app.models.testcase import TestCase
from app.schemas.suite_schema import TestSuiteCreate, TestSuiteUpdate


def _validate_cases(db: Session, case_ids: list[int]) -> None:
    rows = db.query(TestCase.id, TestCase.enabled).filter(TestCase.id.in_(case_ids)).all()
    found = {row.id for row in rows}
    missing = sorted(set(case_ids) - found)
    if missing:
        raise HTTPException(status_code=404, detail=f"测试用例不存在: {missing}")
    disabled = sorted(row.id for row in rows if not row.enabled)
    if disabled:
        raise HTTPException(status_code=422, detail=f"测试用例已禁用: {disabled}")


def _replace_cases(db: Session, suite_id: int, case_ids: list[int]) -> None:
    db.query(TestSuiteCase).filter(TestSuiteCase.suite_id == suite_id).delete()
    db.add_all(
        [
            TestSuiteCase(suite_id=suite_id, case_id=case_id, position=position)
            for position, case_id in enumerate(case_ids, start=1)
        ]
    )


def _case_ids(db: Session, suite_id: int) -> list[int]:
    rows = (
        db.query(TestSuiteCase.case_id)
        .filter(TestSuiteCase.suite_id == suite_id)
        .order_by(TestSuiteCase.position.asc())
        .all()
    )
    return [row.case_id for row in rows]


def serialize_suite(db: Session, suite: TestSuite) -> dict:
    return {
        "id": suite.id,
        "name": suite.name,
        "description": suite.description,
        "case_ids": _case_ids(db, suite.id),
        "fail_fast": suite.fail_fast,
        "analyze_by_ai": suite.analyze_by_ai,
        "enabled": suite.enabled,
        "created_at": suite.created_at,
        "updated_at": suite.updated_at,
    }


def create_suite(db: Session, payload: TestSuiteCreate) -> dict:
    if db.query(TestSuite).filter(TestSuite.name == payload.name).first():
        raise HTTPException(status_code=409, detail="回归套件名称已存在")
    _validate_cases(db, payload.case_ids)
    suite = TestSuite(**payload.model_dump(exclude={"case_ids"}))
    db.add(suite)
    db.flush()
    _replace_cases(db, suite.id, payload.case_ids)
    db.commit()
    db.refresh(suite)
    return serialize_suite(db, suite)


def list_suites(db: Session, *, enabled: bool | None = None) -> list[dict]:
    query = db.query(TestSuite)
    if enabled is not None:
        query = query.filter(TestSuite.enabled == enabled)
    suites = query.order_by(TestSuite.id.desc()).all()
    return [serialize_suite(db, suite) for suite in suites]


def get_suite_model(db: Session, suite_id: int) -> TestSuite:
    suite = db.get(TestSuite, suite_id)
    if suite is None:
        raise HTTPException(status_code=404, detail="回归套件不存在")
    return suite


def get_suite(db: Session, suite_id: int) -> dict:
    return serialize_suite(db, get_suite_model(db, suite_id))


def update_suite(db: Session, suite_id: int, payload: TestSuiteUpdate) -> dict:
    suite = get_suite_model(db, suite_id)
    values = payload.model_dump(exclude_unset=True)
    if "name" in values:
        duplicate = (
            db.query(TestSuite)
            .filter(TestSuite.name == values["name"], TestSuite.id != suite_id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="回归套件名称已存在")
    case_ids = values.pop("case_ids", None)
    if case_ids is not None:
        _validate_cases(db, case_ids)
        _replace_cases(db, suite_id, case_ids)
    for key, value in values.items():
        setattr(suite, key, value)
    db.commit()
    db.refresh(suite)
    return serialize_suite(db, suite)


def delete_suite(db: Session, suite_id: int) -> None:
    suite = get_suite_model(db, suite_id)
    run_count = db.query(TestRun).filter(TestRun.suite_id == suite_id).count()
    if run_count:
        raise HTTPException(status_code=409, detail=f"该套件已有 {run_count} 次历史执行，不允许删除")
    db.query(TestSuiteCase).filter(TestSuiteCase.suite_id == suite_id).delete()
    db.delete(suite)
    db.commit()


def suite_case_ids(db: Session, suite_id: int) -> tuple[TestSuite, list[int]]:
    suite = get_suite_model(db, suite_id)
    if not suite.enabled:
        raise HTTPException(status_code=422, detail="回归套件已禁用")
    case_ids = _case_ids(db, suite_id)
    if not case_ids:
        raise HTTPException(status_code=422, detail="回归套件没有测试用例")
    _validate_cases(db, case_ids)
    return suite, case_ids


def suite_trends(db: Session, suite_id: int, limit: int) -> dict:
    get_suite_model(db, suite_id)
    runs = (
        db.query(TestRun)
        .filter(TestRun.suite_id == suite_id, TestRun.status.in_(["passed", "failed"]))
        .order_by(TestRun.id.desc())
        .limit(limit)
        .all()
    )
    items = []
    for run in runs:
        duration_ms = None
        if run.started_at and run.finished_at:
            duration_ms = max(0, round((run.finished_at - run.started_at).total_seconds() * 1000))
        items.append(
            {
                "run_id": run.id,
                "status": run.status,
                "total": run.total,
                "passed": run.passed,
                "failed": run.failed,
                "pass_rate": round(run.passed * 100 / run.total, 2) if run.total else 0.0,
                "duration_ms": duration_ms,
                "created_at": run.created_at,
            }
        )
    return {
        "suite_id": suite_id,
        "run_count": len(items),
        "latest_pass_rate": items[0]["pass_rate"] if items else None,
        "items": items,
    }
