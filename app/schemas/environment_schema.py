from typing import Any

from pydantic import BaseModel, Field, field_validator
from app.utils.redaction import is_sensitive_key


class EnvironmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: str = ""
    variables: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, Any] = Field(default_factory=dict, exclude=True)
    enabled: bool = True

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if value and not value.startswith(("http://", "https://")):
            raise ValueError("base_url 必须为空或以 http://、https:// 开头")
        return value

    @field_validator("variables")
    @classmethod
    def keep_secrets_out_of_plain_variables(cls, value: dict[str, Any]) -> dict[str, Any]:
        sensitive = [key for key in value if is_sensitive_key(key)]
        if sensitive:
            raise ValueError(f"敏感变量必须放入 secrets 字段: {sensitive}")
        return value


class EnvironmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    base_url: str | None = None
    variables: dict[str, Any] | None = None
    headers: dict[str, Any] | None = None
    secrets: dict[str, Any] | None = Field(default=None, exclude=True)
    enabled: bool | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("字段不允许为 null，省略该字段即可")
        return value

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        value = value.strip().rstrip("/")
        if value and not value.startswith(("http://", "https://")):
            raise ValueError("base_url 必须为空或以 http://、https:// 开头")
        return value

    @field_validator("variables")
    @classmethod
    def keep_secrets_out_of_plain_variables(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        sensitive = [key for key in value if is_sensitive_key(key)]
        if sensitive:
            raise ValueError(f"敏感变量必须放入 secrets 字段: {sensitive}")
        return value


class EnvironmentOut(BaseModel):
    id: int
    name: str
    base_url: str
    variables: dict[str, Any]
    headers: dict[str, Any]
    enabled: bool
    secret_keys: list[str] = Field(default_factory=list)
