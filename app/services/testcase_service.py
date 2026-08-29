from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.interface import ApiInterface
from app.models.testcase import TestCase
from app.models.result import TestResult
from app.models.suite import TestSuiteCase
from app.schemas.testcase_schema import TestCaseCreate, TestCaseUpdate


def _validate_dependencies(db: Session, case_id: int | None, dependencies: list[int]) -> None:
    unique = set(dependencies)
    if len(unique) != len(dependencies):
        raise HTTPException(status_code=422, detail="dependencies 不允许重复")
    if case_id is not None and case_id in unique:
        raise HTTPException(status_code=422, detail="测试用例不能依赖自身")
    if not unique:
        return
    found = {row[0] for row in db.query(TestCase.id).filter(TestCase.id.in_(unique)).all()}
    missing = sorted(unique - found)
    if missing:
        raise HTTPException(status_code=404, detail=f"依赖用例不存在: {missing}")


def create_case(db: Session, payload: TestCaseCreate) -> TestCase:
    if db.get(ApiInterface, payload.interface_id) is None:
        raise HTTPException(status_code=404, detail="接口不存在")
    _validate_dependencies(db, None, payload.dependencies)
    item = TestCase(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_cases(
    db: Session,
    interface_id: int | None = None,
    enabled: bool | None = None,
    offset: int = 0,
    limit: int = 200,
) -> list[TestCase]:
    query = db.query(TestCase)
    if interface_id is not None:
        query = query.filter(TestCase.interface_id == interface_id)
    if enabled is not None:
        query = query.filter(TestCase.enabled == enabled)
    return query.order_by(TestCase.id.desc()).offset(offset).limit(limit).all()


def search_cases(
    db: Session,
    keyword: str = "",
    interface_id: int | None = None,
    enabled: bool | None = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[TestCase], int]:
    query = db.query(TestCase)
    keyword = keyword.strip()
    if keyword:
        query = query.filter(TestCase.case_name.ilike(f"%{keyword}%"))
    if interface_id is not None:
        query = query.filter(TestCase.interface_id == interface_id)
    if enabled is not None:
        query = query.filter(TestCase.enabled == enabled)
    total = query.count()
    items = (
        query.order_by(TestCase.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_case(db: Session, case_id: int) -> TestCase:
    item = db.get(TestCase, case_id)
    if not item:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    return item


def update_case(db: Session, case_id: int, payload: TestCaseUpdate) -> TestCase:
    item = get_case(db, case_id)
    values = payload.model_dump(exclude_unset=True)
    if "dependencies" in values:
        _validate_dependencies(db, case_id, values["dependencies"] or [])
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_case(db: Session, case_id: int) -> None:
    item = get_case(db, case_id)
    dependent = db.query(TestCase).all()
    used_by = [case.id for case in dependent if case_id in (case.dependencies or [])]
    if used_by:
        raise HTTPException(status_code=409, detail=f"该用例仍被以下用例依赖: {used_by}")
    suite_count = db.query(TestSuiteCase).filter(TestSuiteCase.case_id == case_id).count()
    if suite_count:
        raise HTTPException(status_code=409, detail=f"该用例仍属于 {suite_count} 个回归套件")
    result_count = db.query(TestResult).filter(TestResult.case_id == case_id).count()
    if result_count:
        raise HTTPException(status_code=409, detail=f"该用例已有 {result_count} 条历史结果，不允许删除")
    db.delete(item)
    db.commit()
