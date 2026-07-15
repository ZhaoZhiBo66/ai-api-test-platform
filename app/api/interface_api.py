from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.schemas.interface_schema import InterfaceCreate, InterfaceOut, InterfaceUpdate
from app.services import interface_service

router = APIRouter(prefix="/interfaces", tags=["接口管理"])


@router.post("", response_model=InterfaceOut, status_code=status.HTTP_201_CREATED)
def create_interface(payload: InterfaceCreate, db: Session = Depends(get_db)):
    return interface_service.create_interface(db, payload)


@router.get("", response_model=list[InterfaceOut])
def list_interfaces(db: Session = Depends(get_db)):
    return interface_service.list_interfaces(db)


@router.get("/{interface_id}", response_model=InterfaceOut)
def get_interface(interface_id: int, db: Session = Depends(get_db)):
    return interface_service.get_interface(db, interface_id)


@router.put("/{interface_id}", response_model=InterfaceOut)
def update_interface(interface_id: int, payload: InterfaceUpdate, db: Session = Depends(get_db)):
    return interface_service.update_interface(db, interface_id, payload)


@router.delete("/{interface_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interface(interface_id: int, db: Session = Depends(get_db)):
    interface_service.delete_interface(db, interface_id)

