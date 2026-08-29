from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.api.security import require_api_key
from app.schemas.interface_schema import InterfaceCreate, InterfaceOut, InterfacePage, InterfaceUpdate
from app.services import interface_service

router = APIRouter(prefix="/interfaces", tags=["接口管理"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=InterfaceOut, status_code=status.HTTP_201_CREATED)
def create_interface(payload: InterfaceCreate, db: Session = Depends(get_db)):
    return interface_service.create_interface(db, payload)


@router.get("", response_model=list[InterfaceOut])
def list_interfaces(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return interface_service.list_interfaces(db, offset, limit)


@router.get("/page", response_model=InterfacePage)
def page_interfaces(
    keyword: str = Query(default="", max_length=100),
    method: str | None = Query(default=None, pattern="^(GET|POST|PUT|PATCH|DELETE)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=5, le=100),
    db: Session = Depends(get_db),
):
    items, total = interface_service.search_interfaces(db, keyword, method, page, page_size)
    pages = max(1, (total + page_size - 1) // page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}


@router.get("/{interface_id}", response_model=InterfaceOut)
def get_interface(interface_id: int, db: Session = Depends(get_db)):
    return interface_service.get_interface(db, interface_id)


@router.put("/{interface_id}", response_model=InterfaceOut)
def update_interface(interface_id: int, payload: InterfaceUpdate, db: Session = Depends(get_db)):
    return interface_service.update_interface(db, interface_id, payload)


@router.delete("/{interface_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interface(interface_id: int, db: Session = Depends(get_db)):
    interface_service.delete_interface(db, interface_id)

