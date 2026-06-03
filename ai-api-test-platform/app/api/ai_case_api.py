from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.openai_client import openai_client
from app.database.db import get_db
from app.schemas.testcase_schema import AIGenerateRequest, AnalyzeRequest, TestCaseOut
from app.services.ai_case_service import generate_and_save_cases, list_cases_by_interface

router = APIRouter(prefix="/ai", tags=["AI能力"])


@router.post("/interfaces/{interface_id}/cases", response_model=list[TestCaseOut])
def generate_cases(interface_id: int, payload: AIGenerateRequest, db: Session = Depends(get_db)):
    return generate_and_save_cases(db, interface_id, payload.input_data, payload.expected_status_code)


@router.get("/interfaces/{interface_id}/cases", response_model=list[TestCaseOut])
def list_cases(interface_id: int, db: Session = Depends(get_db)):
    return list_cases_by_interface(db, interface_id)


@router.post("/analyze-result")
def analyze_result(payload: AnalyzeRequest):
    analysis = openai_client.analyze_result(
        status_code=payload.status_code,
        response=payload.response,
        assertion_message=payload.assertion_message,
    )
    return {"analysis": analysis}

