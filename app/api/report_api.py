from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.services.report_service import run_allure

router = APIRouter(prefix="/reports", tags=["测试报告"])


@router.post("/allure")
def generate_allure_report(db: Session = Depends(get_db)):
    return run_allure(db)

