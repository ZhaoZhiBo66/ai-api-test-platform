from sqlalchemy.orm import Session

from app.ai.openai_client import openai_client
from app.models.testcase import TestCase
from app.services.interface_service import get_interface


def generate_and_save_cases(
    db: Session,
    interface_id: int,
    input_data: dict,
    expected_status_code: int = 200,
) -> list[TestCase]:
    get_interface(db, interface_id)
    ai_cases = openai_client.generate_cases(input_data)
    saved_cases: list[TestCase] = []

    for item in ai_cases:
        case = TestCase(
            interface_id=interface_id,
            case_name=item.get("case_name", "AI生成用例"),
            data=item.get("data", input_data),
            expected_status_code=item.get("expected_status_code", expected_status_code),
            expected_json=item.get("expected_json", {}),
            sql_check=item.get("sql_check", {}),
        )
        db.add(case)
        saved_cases.append(case)

    db.commit()
    for case in saved_cases:
        db.refresh(case)
    return saved_cases


def list_cases_by_interface(db: Session, interface_id: int) -> list[TestCase]:
    return db.query(TestCase).filter(TestCase.interface_id == interface_id).order_by(TestCase.id.desc()).all()

