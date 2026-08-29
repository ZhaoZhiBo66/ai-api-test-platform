from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.security import require_admin, require_api_key
from app.database.db import get_db
from app.services.audit_service import list_audit_logs


router = APIRouter(
    prefix="/audit-logs",
    tags=["审计日志"],
    dependencies=[Depends(require_api_key), Depends(require_admin)],
)


@router.get("")
def get_audit_logs(
    actor: str | None = None,
    method: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    total, items = list_audit_logs(
        db, actor=actor, method=method, offset=offset, limit=limit
    )
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "id": item.id,
                "request_id": item.request_id,
                "actor": item.actor,
                "role": item.role,
                "method": item.method,
                "path": item.path,
                "status_code": item.status_code,
                "duration_ms": item.duration_ms,
                "client_ip": item.client_ip,
                "created_at": item.created_at,
            }
            for item in items
        ],
    }
