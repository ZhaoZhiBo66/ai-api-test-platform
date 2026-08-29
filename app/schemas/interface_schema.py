from typing import Any

from pydantic import BaseModel, Field, HttpUrl, TypeAdapter, field_validator


_HTTP_URL = TypeAdapter(HttpUrl)


def _validate_interface_url(value: str) -> str:
    value = str(value).strip()
    if value.startswith("/"):
        return value
    return str(_HTTP_URL.validate_python(value))


class InterfaceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: str
    method: str = Field(..., pattern="^(GET|POST|PUT|DELETE|PATCH)$")
    headers: dict[str, Any] = Field(default_factory=dict)
    body: dict[str, Any] = Field(default_factory=dict)
    spec: dict[str, Any] = Field(default_factory=dict)

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, value: Any) -> str:
        return _validate_interface_url(value)


class InterfaceCreate(InterfaceBase):
    pass


class InterfaceUpdate(BaseModel):
    # None means "field omitted", never "set this column to NULL": no column on
    # ApiInterface is nullable. Validators do not run on defaults, so an omitted
    # field keeps its None and is dropped later by model_dump(exclude_unset=True),
    # while an explicit null reaches the validator below and is rejected.
    name: str | None = Field(default=None, min_length=1, max_length=100)
    url: str | None = None
    method: str | None = Field(default=None, pattern="^(GET|POST|PUT|DELETE|PATCH)$")
    headers: dict[str, Any] | None = None
    body: dict[str, Any] | None = None
    spec: dict[str, Any] | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("字段不允许为 null，省略该字段即可")
        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        return _validate_interface_url(value) if value is not None else None


class InterfaceOut(InterfaceBase):
    id: int

    model_config = {"from_attributes": True}


class InterfacePage(BaseModel):
    items: list[InterfaceOut]
    total: int
    page: int
    page_size: int
    pages: int

