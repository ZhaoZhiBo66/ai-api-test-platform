from typing import Any

from pydantic import BaseModel, Field, field_validator


class GeneratedCase(BaseModel):
    case_name: str = Field(min_length=1, max_length=150)
    data: dict[str, Any] = Field(default_factory=dict)
    expected_status_code: int = Field(default=200, ge=100, le=599)
    expected_json: dict[str, Any] = Field(default_factory=dict)
    sql_check: dict[str, Any] = Field(default_factory=dict)

    @field_validator("case_name")
    @classmethod
    def strip_case_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("用例名称不能为空")
        return value


class GeneratedCaseBatch(BaseModel):
    cases: list[GeneratedCase] = Field(min_length=1, max_length=100)
