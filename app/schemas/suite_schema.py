from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TestSuiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=2000)
    case_ids: list[int] = Field(min_length=1, max_length=500)
    fail_fast: bool = False
    analyze_by_ai: bool = False
    enabled: bool = True

    @field_validator("case_ids")
    @classmethod
    def unique_case_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("case_ids 不允许重复")
        return value


class TestSuiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    case_ids: list[int] | None = Field(default=None, min_length=1, max_length=500)
    fail_fast: bool | None = None
    analyze_by_ai: bool | None = None
    enabled: bool | None = None

    @field_validator("case_ids")
    @classmethod
    def unique_case_ids(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("case_ids 不允许重复")
        return value


class TestSuiteOut(BaseModel):
    id: int
    name: str
    description: str
    case_ids: list[int]
    fail_fast: bool
    analyze_by_ai: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime


class SuiteRunRequest(BaseModel):
    environment_id: int | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    fail_fast: bool | None = None
    analyze_by_ai: bool | None = None


class SuiteTrendItem(BaseModel):
    run_id: int
    status: str
    total: int
    passed: int
    failed: int
    pass_rate: float
    duration_ms: int | None
    created_at: datetime


class SuiteTrendOut(BaseModel):
    suite_id: int
    run_count: int
    latest_pass_rate: float | None
    items: list[SuiteTrendItem]
