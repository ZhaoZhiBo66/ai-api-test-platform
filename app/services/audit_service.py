from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def list_audit_logs(
    db: Session,
    *,
    actor: str | None = None,
    method: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> tuple[int, list[AuditLog]]:
    query = db.query(AuditLog)
    if actor:
        query = query.filter(AuditLog.actor == actor)
    if method:
        query = query.filter(AuditLog.method == method.upper())
    total = query.count()
    return total, query.order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()
