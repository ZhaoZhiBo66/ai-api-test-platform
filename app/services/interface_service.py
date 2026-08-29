from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.interface import ApiInterface
from app.models.testcase import TestCase
from app.models.result import TestRun
from app.schemas.interface_schema import InterfaceCreate, InterfaceUpdate


def create_interface(db: Session, payload: InterfaceCreate) -> ApiInterface:
    item = ApiInterface(
        name=payload.name,
        url=payload.url,
        method=payload.method.upper(),
        headers=payload.headers,
        body=payload.body,
        spec=payload.spec,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_interfaces(db: Session, offset: int = 0, limit: int = 200) -> list[ApiInterface]:
    return db.query(ApiInterface).order_by(ApiInterface.id.desc()).offset(offset).limit(limit).all()


def search_interfaces(
    db: Session,
    keyword: str = "",
    method: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[ApiInterface], int]:
    query = db.query(ApiInterface)
    keyword = keyword.strip()
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(or_(ApiInterface.name.ilike(pattern), ApiInterface.url.ilike(pattern)))
    if method:
        query = query.filter(ApiInterface.method == method.upper())
    total = query.count()
    items = (
        query.order_by(ApiInterface.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_interface(db: Session, interface_id: int) -> ApiInterface:
    item = db.get(ApiInterface, interface_id)
    if not item:
        raise HTTPException(status_code=404, detail="接口不存在")
    return item


def update_interface(db: Session, interface_id: int, payload: InterfaceUpdate) -> ApiInterface:
    item = get_interface(db, interface_id)
    data = payload.model_dump(exclude_unset=True)
    if "method" in data and data["method"] is not None:
        data["method"] = data["method"].upper()
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_interface(db: Session, interface_id: int) -> None:
    item = get_interface(db, interface_id)
    case_count = db.query(TestCase).filter(TestCase.interface_id == interface_id).count()
    if case_count:
        raise HTTPException(
            status_code=409,
            detail=f"该接口仍关联 {case_count} 条测试用例，请先删除用例或执行归档",
        )
    run_count = db.query(TestRun).filter(TestRun.interface_id == interface_id).count()
    if run_count:
        raise HTTPException(
            status_code=409,
            detail=f"该接口仍关联 {run_count} 条历史测试任务，不允许删除",
        )
    db.delete(item)
    db.commit()

