from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.environment import TestEnvironment
from app.models.result import TestRun
from app.schemas.environment_schema import EnvironmentCreate, EnvironmentUpdate
from app.utils.encryption import decrypt_mapping, encrypt_mapping
from app.utils.redaction import redact


def create_environment(db: Session, payload: EnvironmentCreate) -> TestEnvironment:
    item = TestEnvironment(
        **payload.model_dump(exclude={"secrets"}),
        secrets_encrypted=encrypt_mapping(payload.secrets),
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="环境名称已存在") from exc
    db.refresh(item)
    return item


def list_environments(db: Session) -> list[TestEnvironment]:
    return db.query(TestEnvironment).order_by(TestEnvironment.id.asc()).all()


def get_environment(db: Session, environment_id: int) -> TestEnvironment:
    item = db.get(TestEnvironment, environment_id)
    if not item:
        raise HTTPException(status_code=404, detail="测试环境不存在")
    return item


def update_environment(db: Session, environment_id: int, payload: EnvironmentUpdate) -> TestEnvironment:
    item = get_environment(db, environment_id)
    values = payload.model_dump(exclude_unset=True, exclude={"secrets"})
    for key, value in values.items():
        setattr(item, key, value)
    if "secrets" in payload.model_fields_set:
        item.secrets_encrypted = encrypt_mapping(payload.secrets or {})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="环境名称已存在") from exc
    db.refresh(item)
    return item


def delete_environment(db: Session, environment_id: int) -> None:
    item = get_environment(db, environment_id)
    run_count = db.query(TestRun).filter(TestRun.environment_id == environment_id).count()
    if run_count:
        raise HTTPException(
            status_code=409,
            detail=f"该环境仍关联 {run_count} 个历史测试任务，不允许删除",
        )
    db.delete(item)
    db.commit()


def environment_secrets(item: TestEnvironment | None) -> dict:
    return decrypt_mapping(item.secrets_encrypted) if item else {}


def public_environment(item: TestEnvironment) -> dict:
    secrets = environment_secrets(item)
    return {
        "id": item.id,
        "name": item.name,
        "base_url": item.base_url,
        "variables": redact(item.variables or {}),
        "headers": redact(item.headers or {}),
        "enabled": item.enabled,
        "secret_keys": sorted(secrets),
    }
