from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.security import require_api_key
from app.database.db import get_db
from app.schemas.openapi_schema import OpenAPIImportRequest, OpenAPIImportResult
from app.services.openapi_service import import_openapi


router = APIRouter(prefix="/openapi", tags=["OpenAPI导入"], dependencies=[Depends(require_api_key)])


@router.post("/import", response_model=OpenAPIImportResult)
def import_openapi_document(payload: OpenAPIImportRequest, db: Session = Depends(get_db)):
    return import_openapi(db, payload)
