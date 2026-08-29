from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.security import require_api_key
from app.database.db import get_db
from app.schemas.testcase_schema import TestCaseCreate, TestCaseOut, TestCasePage, TestCaseUpdate
from app.services import testcase_service


router = APIRouter(prefix="/cases", tags=["测试用例"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=TestCaseOut, status_code=status.HTTP_201_CREATED)
def create_case(payload: TestCaseCreate, db: Session = Depends(get_db)):
    return testcase_service.create_case(db, payload)


@router.get("", response_model=list[TestCaseOut])
def list_cases(
    interface_id: int | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return testcase_service.list_cases(db, interface_id, enabled, offset, limit)


@router.get("/page", response_model=TestCasePage)
def page_cases(
    keyword: str = Query(default="", max_length=150),
    interface_id: int | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=5, le=100),
    db: Session = Depends(get_db),
):
    items, total = testcase_service.search_cases(
        db, keyword, interface_id, enabled, page, page_size
    )
    pages = max(1, (total + page_size - 1) // page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}


@router.get("/{case_id}", response_model=TestCaseOut)
def get_case(case_id: int, db: Session = Depends(get_db)):
    return testcase_service.get_case(db, case_id)


@router.put("/{case_id}", response_model=TestCaseOut)
def update_case(case_id: int, payload: TestCaseUpdate, db: Session = Depends(get_db)):
    return testcase_service.update_case(db, case_id, payload)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(case_id: int, db: Session = Depends(get_db)):
    testcase_service.delete_case(db, case_id)
