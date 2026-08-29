from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.api.security import require_api_key
from app.services.report_service import generate_allure_from_run

router = APIRouter(prefix="/reports", tags=["测试报告"], dependencies=[Depends(require_api_key)])


@router.post("/allure")
def generate_allure_report(
    run_id: int,
    db: Session = Depends(get_db),
):
    return generate_allure_from_run(db, run_id)

