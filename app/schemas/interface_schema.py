from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class InterfaceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: HttpUrl
    method: str = Field(..., pattern="^(GET|POST|PUT|DELETE|PATCH)$")
    headers: dict[str, Any] = Field(default_factory=dict)
    body: dict[str, Any] = Field(default_factory=dict)


class InterfaceCreate(InterfaceBase):
    pass


class InterfaceUpdate(BaseModel):
    # None means "field omitted", never "set this column to NULL": no column on
    # ApiInterface is nullable. Validators do not run on defaults, so an omitted
    # field keeps its None and is dropped later by model_dump(exclude_unset=True),
    # while an explicit null reaches the validator below and is rejected.
    name: str | None = Field(default=None, min_length=1, max_length=100)
    url: HttpUrl | None = None
    method: str | None = Field(default=None, pattern="^(GET|POST|PUT|DELETE|PATCH)$")
    headers: dict[str, Any] | None = None
    body: dict[str, Any] | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("字段不允许为 null，省略该字段即可")
        return value


class InterfaceOut(InterfaceBase):
    id: int

    model_config = {"from_attributes": True}

