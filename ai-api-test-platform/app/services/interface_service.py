from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.interface import ApiInterface
from app.schemas.interface_schema import InterfaceCreate, InterfaceUpdate


def create_interface(db: Session, payload: InterfaceCreate) -> ApiInterface:
    item = ApiInterface(
        name=payload.name,
        url=str(payload.url),
        method=payload.method.upper(),
        headers=payload.headers,
        body=payload.body,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_interfaces(db: Session) -> list[ApiInterface]:
    return db.query(ApiInterface).order_by(ApiInterface.id.desc()).all()


def get_interface(db: Session, interface_id: int) -> ApiInterface:
    item = db.get(ApiInterface, interface_id)
    if not item:
        raise HTTPException(status_code=404, detail="接口不存在")
    return item


def update_interface(db: Session, interface_id: int, payload: InterfaceUpdate) -> ApiInterface:
    item = get_interface(db, interface_id)
    data = payload.model_dump(exclude_unset=True)
    if "url" in data and data["url"] is not None:
        data["url"] = str(data["url"])
    if "method" in data and data["method"] is not None:
        data["method"] = data["method"].upper()
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_interface(db: Session, interface_id: int) -> None:
    item = get_interface(db, interface_id)
    db.delete(item)
    db.commit()

