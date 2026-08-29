from typing import Any

from pydantic import BaseModel, Field


class OpenAPIImportRequest(BaseModel):
    document: dict[str, Any]
    base_url: str | None = None
    store_relative_urls: bool = True
    overwrite_existing: bool = False
    generate_schema_cases: bool = True
    default_negative_status_code: int = Field(default=400, ge=100, le=599)


class OpenAPIImportResult(BaseModel):
    created_interfaces: int
    updated_interfaces: int
    skipped_interfaces: int
    generated_cases: int
    interface_ids: list[int]
