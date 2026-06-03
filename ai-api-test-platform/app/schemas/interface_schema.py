from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class InterfaceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: HttpUrl
    method: str = Field(..., pattern="^(GET|POST|PUT|DELETE|PATCH)$")
    headers: dict[str, Any] = Field(default_factory=dict)
    body: dict[str, Any] = Field(default_factory=dict)


class InterfaceCreate(InterfaceBase):
    pass


class InterfaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    url: HttpUrl | None = None
    method: str | None = Field(default=None, pattern="^(GET|POST|PUT|DELETE|PATCH)$")
    headers: dict[str, Any] | None = None
    body: dict[str, Any] | None = None


class InterfaceOut(InterfaceBase):
    id: int

    model_config = {"from_attributes": True}

