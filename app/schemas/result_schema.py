from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TestRunOut(BaseModel):
    id: int
    interface_id: int | None
    suite_id: int | None
    environment_id: int | None
    status: str
    total: int
    passed: int
    failed: int
    ai_summary: str
    variables: dict[str, Any]
    cancel_requested: bool
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class TestResultOut(BaseModel):
    id: int
    run_id: int
    case_id: int
    case_name: str
    status: str
    status_code: int | None
    request_data: dict[str, Any]
    response_data: dict[str, Any]
    response_headers: dict[str, Any]
    duration_ms: int | None
    extracted_variables: dict[str, Any]
    attempt: int
    assertion_message: str
    ai_analysis: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RunPage(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[TestRunOut]


class ResultPage(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[TestResultOut]


class AsyncRunAccepted(BaseModel):
    run_id: int
    status: str = "queued"


class RunListQuery(BaseModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)
