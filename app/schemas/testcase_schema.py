from typing import Any

from pydantic import BaseModel, Field, field_validator


class AIGenerateRequest(BaseModel):
    input_data: dict[str, Any] = Field(..., description="基础请求参数")
    expected_status_code: int | None = Field(
        default=None,
        ge=100,
        le=599,
        description="留空时允许生成器为正向和负向用例分别判断预期状态码",
    )


class TestCaseCreate(BaseModel):
    interface_id: int
    case_name: str
    data: dict[str, Any] = Field(default_factory=dict)
    expected_status_code: int = 200
    expected_json: dict[str, Any] = Field(default_factory=dict)
    sql_check: dict[str, Any] = Field(default_factory=dict)
    assertions: list[dict[str, Any]] = Field(default_factory=list)
    extractors: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: list[int] = Field(default_factory=list)
    request_config: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = Field(default=0, ge=0, le=5)
    enabled: bool = True


class TestCaseUpdate(BaseModel):
    case_name: str | None = Field(default=None, min_length=1, max_length=150)
    data: dict[str, Any] | None = None
    expected_status_code: int | None = Field(default=None, ge=100, le=599)
    expected_json: dict[str, Any] | None = None
    sql_check: dict[str, Any] | None = None
    assertions: list[dict[str, Any]] | None = None
    extractors: list[dict[str, Any]] | None = None
    dependencies: list[int] | None = None
    request_config: dict[str, Any] | None = None
    retry_count: int | None = Field(default=None, ge=0, le=5)
    enabled: bool | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("字段不允许为 null，省略该字段即可")
        return value


class TestCaseOut(TestCaseCreate):
    id: int

    model_config = {"from_attributes": True}


class TestCasePage(BaseModel):
    items: list[TestCaseOut]
    total: int
    page: int
    page_size: int
    pages: int


class RunRequest(BaseModel):
    interface_id: int | None = None
    case_ids: list[int] = Field(default_factory=list)
    environment_id: int | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    fail_fast: bool = False
    analyze_by_ai: bool = True


class AnalyzeRequest(BaseModel):
    status_code: int
    response: dict[str, Any]
    assertion_message: str = ""

