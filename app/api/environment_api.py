from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.security import require_api_key
from app.database.db import get_db
from app.schemas.environment_schema import EnvironmentCreate, EnvironmentOut, EnvironmentUpdate
from app.services import environment_service


router = APIRouter(
    prefix="/environments",
    tags=["测试环境"],
    dependencies=[Depends(require_api_key)],
)


@router.post("", response_model=EnvironmentOut, status_code=status.HTTP_201_CREATED)
def create_environment(payload: EnvironmentCreate, db: Session = Depends(get_db)):
    return environment_service.public_environment(environment_service.create_environment(db, payload))


@router.get("", response_model=list[EnvironmentOut])
def list_environments(db: Session = Depends(get_db)):
    return [environment_service.public_environment(item) for item in environment_service.list_environments(db)]


@router.get("/{environment_id}", response_model=EnvironmentOut)
def get_environment(environment_id: int, db: Session = Depends(get_db)):
    return environment_service.public_environment(environment_service.get_environment(db, environment_id))


@router.put("/{environment_id}", response_model=EnvironmentOut)
def update_environment(environment_id: int, payload: EnvironmentUpdate, db: Session = Depends(get_db)):
    return environment_service.public_environment(
        environment_service.update_environment(db, environment_id, payload)
    )


@router.delete("/{environment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_environment(environment_id: int, db: Session = Depends(get_db)):
    environment_service.delete_environment(db, environment_id)
