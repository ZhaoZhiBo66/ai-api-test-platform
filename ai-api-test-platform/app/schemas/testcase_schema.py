from typing import Any

from pydantic import BaseModel, Field


class AIGenerateRequest(BaseModel):
    input_data: dict[str, Any] = Field(..., description="基础请求参数")
    expected_status_code: int = 200


class TestCaseCreate(BaseModel):
    interface_id: int
    case_name: str
    data: dict[str, Any] = Field(default_factory=dict)
    expected_status_code: int = 200
    expected_json: dict[str, Any] = Field(default_factory=dict)
    sql_check: dict[str, Any] = Field(default_factory=dict)


class TestCaseOut(TestCaseCreate):
    id: int

    model_config = {"from_attributes": True}


class RunRequest(BaseModel):
    interface_id: int | None = None
    case_ids: list[int] = Field(default_factory=list)
    analyze_by_ai: bool = True


class AnalyzeRequest(BaseModel):
    status_code: int
    response: dict[str, Any]
    assertion_message: str = ""

